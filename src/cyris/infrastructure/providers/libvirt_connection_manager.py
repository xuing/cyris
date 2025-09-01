"""
LibVirt Connection Manager

Centralized connection management for libvirt operations with connection pooling,
automatic reconnection, thread safety, and performance optimization.

Usage:
    # Basic usage
    manager = LibvirtConnectionManager()
    conn = manager.get_connection()
    domain = manager.get_domain("vm-name")
    
    # URI-specific connections
    manager = LibvirtConnectionManager("qemu+ssh://remote/system")
    
    # Connection with custom timeout
    manager = LibvirtConnectionManager(timeout=60)
"""

import libvirt
import threading
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import contextmanager
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a libvirt connection"""
    uri: str
    connection: libvirt.virConnect
    created_at: datetime
    last_used: datetime = field(default_factory=datetime.now)
    use_count: int = 0
    is_alive: bool = True
    
    def update_usage(self):
        """Update last used time and increment usage count"""
        self.last_used = datetime.now()
        self.use_count += 1


@dataclass
class DomainInfo:
    """Enhanced domain information"""
    name: str
    uuid: str
    state: Tuple[int, int]  # (state, reason)
    id: int  # -1 if not running
    max_memory: int
    memory: int
    vcpus: int
    cpu_time: int
    
    @property
    def state_str(self) -> str:
        """Human-readable domain state"""
        state_map = {
            libvirt.VIR_DOMAIN_NOSTATE: "no state",
            libvirt.VIR_DOMAIN_RUNNING: "running", 
            libvirt.VIR_DOMAIN_BLOCKED: "blocked",
            libvirt.VIR_DOMAIN_PAUSED: "paused",
            libvirt.VIR_DOMAIN_SHUTDOWN: "shutdown",
            libvirt.VIR_DOMAIN_SHUTOFF: "shutoff",
            libvirt.VIR_DOMAIN_CRASHED: "crashed",
            libvirt.VIR_DOMAIN_PMSUSPENDED: "suspended"
        }
        return state_map.get(self.state[0], f"unknown({self.state[0]})")
    
    @property
    def is_active(self) -> bool:
        """Check if domain is active (running)"""
        return self.state[0] == libvirt.VIR_DOMAIN_RUNNING


class LibvirtConnectionError(Exception):
    """Raised when libvirt connection fails"""
    pass


class LibvirtDomainError(Exception):
    """Raised when domain operation fails"""
    pass


class LibvirtConnectionManager:
    """
    Thread-safe libvirt connection manager with pooling and auto-reconnection.
    
    Features:
    - Connection pooling and reuse
    - Automatic reconnection on failure
    - Thread-safe operations
    - Connection health monitoring
    - Performance optimizations
    """
    
    def __init__(
        self, 
        uri: str = "qemu:///system",
        timeout: int = 30,
        max_connections: int = 5,
        connection_ttl: int = 3600  # 1 hour
    ):
        """
        Initialize connection manager.
        
        Args:
            uri: LibVirt connection URI
            timeout: Connection timeout in seconds
            max_connections: Maximum concurrent connections
            connection_ttl: Connection time-to-live in seconds
        """
        self.uri = uri
        self.timeout = timeout
        self.max_connections = max_connections
        self.connection_ttl = connection_ttl
        
        # Thread-safe connection pool
        self._connections: Dict[str, ConnectionInfo] = {}
        self._lock = threading.RLock()
        
        # Connection statistics
        self.stats = {
            'connections_created': 0,
            'connections_reused': 0,
            'reconnections': 0,
            'errors': 0
        }
        
        # Test initial connection
        self._test_connection()
    
    def _test_connection(self) -> None:
        """Test initial connection to ensure libvirt is available"""
        try:
            test_conn = libvirt.open(self.uri)
            if test_conn is None:
                raise LibvirtConnectionError(f"Failed to connect to {self.uri}")
            
            # Test basic operation
            hostname = test_conn.getHostname()
            logger.info(f"Successfully connected to libvirt: {hostname} ({self.uri})")
            
            test_conn.close()
            
        except libvirt.libvirtError as e:
            logger.error(f"LibVirt connection test failed: {e}")
            raise LibvirtConnectionError(f"LibVirt not available: {e}")
        except Exception as e:
            logger.error(f"Unexpected error testing libvirt connection: {e}")
            raise LibvirtConnectionError(f"Connection test failed: {e}")
    
    def get_connection(self, uri: Optional[str] = None) -> libvirt.virConnect:
        """
        Get a libvirt connection, reusing existing connections when possible.
        
        Args:
            uri: Optional URI override
            
        Returns:
            Active libvirt connection
            
        Raises:
            LibvirtConnectionError: If connection fails
        """
        target_uri = uri or self.uri
        
        with self._lock:
            # Try to reuse existing connection
            if target_uri in self._connections:
                conn_info = self._connections[target_uri]
                
                # Check if connection is still alive and not expired
                if self._is_connection_valid(conn_info):
                    conn_info.update_usage()
                    self.stats['connections_reused'] += 1
                    return conn_info.connection
                else:
                    # Clean up dead connection
                    try:
                        conn_info.connection.close()
                    except:
                        pass
                    del self._connections[target_uri]
            
            # Create new connection
            return self._create_connection(target_uri)
    
    def _create_connection(self, uri: str) -> libvirt.virConnect:
        """Create new libvirt connection"""
        try:
            # Create connection
            conn = libvirt.open(uri)
            if conn is None:
                raise LibvirtConnectionError(f"Failed to connect to {uri}")
            
            # Store connection info
            conn_info = ConnectionInfo(
                uri=uri,
                connection=conn,
                created_at=datetime.now()
            )
            
            # Clean up oldest connections if at limit
            if len(self._connections) >= self.max_connections:
                self._cleanup_old_connections()
            
            self._connections[uri] = conn_info
            self.stats['connections_created'] += 1
            
            logger.debug(f"Created new libvirt connection: {uri}")
            return conn
            
        except libvirt.libvirtError as e:
            self.stats['errors'] += 1
            logger.error(f"Failed to create libvirt connection to {uri}: {e}")
            raise LibvirtConnectionError(f"Connection failed: {e}")
    
    def _is_connection_valid(self, conn_info: ConnectionInfo) -> bool:
        """Check if connection is still valid"""
        try:
            # Check TTL
            age = datetime.now() - conn_info.created_at
            if age.total_seconds() > self.connection_ttl:
                logger.debug(f"Connection expired: {conn_info.uri}")
                return False
            
            # Test connection
            conn_info.connection.getHostname()
            return True
            
        except (libvirt.libvirtError, AttributeError):
            logger.debug(f"Connection test failed: {conn_info.uri}")
            return False
    
    def _cleanup_old_connections(self) -> None:
        """Clean up oldest connections to make room for new ones"""
        if not self._connections:
            return
            
        # Sort by last used time
        oldest = min(self._connections.values(), key=lambda x: x.last_used)
        
        try:
            oldest.connection.close()
        except:
            pass
        
        del self._connections[oldest.uri]
        logger.debug(f"Cleaned up old connection: {oldest.uri}")
    
    def get_domain(self, domain_name: str, uri: Optional[str] = None) -> libvirt.virDomain:
        """
        Get domain by name.
        
        Args:
            domain_name: Name of the domain
            uri: Optional URI override
            
        Returns:
            LibVirt domain object
            
        Raises:
            LibvirtDomainError: If domain not found or operation fails
        """
        try:
            conn = self.get_connection(uri)
            domain = conn.lookupByName(domain_name)
            return domain
            
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                raise LibvirtDomainError(f"Domain not found: {domain_name}")
            else:
                raise LibvirtDomainError(f"Failed to lookup domain {domain_name}: {e}")
    
    def list_domains(
        self, 
        active_only: bool = False, 
        uri: Optional[str] = None
    ) -> List[libvirt.virDomain]:
        """
        List all domains.
        
        Args:
            active_only: If True, only return running domains
            uri: Optional URI override
            
        Returns:
            List of domain objects
        """
        try:
            conn = self.get_connection(uri)
            
            if active_only:
                domain_ids = conn.listDomainsID()
                domains = [conn.lookupByID(domain_id) for domain_id in domain_ids]
            else:
                domains = conn.listAllDomains()
            
            return domains
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to list domains: {e}")
            return []
    
    def get_domain_info(self, domain_name: str, uri: Optional[str] = None) -> DomainInfo:
        """
        Get comprehensive domain information.
        
        Args:
            domain_name: Name of the domain
            uri: Optional URI override
            
        Returns:
            Enhanced domain information
        """
        domain = self.get_domain(domain_name, uri)
        
        try:
            state = domain.state()
            info = domain.info()
            domain_id = domain.ID() if domain.isActive() else -1
            
            return DomainInfo(
                name=domain.name(),
                uuid=domain.UUIDString(),
                state=state,
                id=domain_id,
                max_memory=info[1],
                memory=info[2],
                vcpus=info[3],
                cpu_time=info[4]
            )
            
        except libvirt.libvirtError as e:
            raise LibvirtDomainError(f"Failed to get domain info for {domain_name}: {e}")
    
    @contextmanager
    def connection_context(self, uri: Optional[str] = None):
        """
        Context manager for connection handling.
        
        Usage:
            with manager.connection_context() as conn:
                # Use connection
                domains = conn.listAllDomains()
        """
        conn = self.get_connection(uri)
        try:
            yield conn
        finally:
            # Connection is managed by pool, no need to close
            pass
    
    def reconnect(self, uri: Optional[str] = None) -> libvirt.virConnect:
        """
        Force reconnection by clearing cached connection.
        
        Args:
            uri: Optional URI override
            
        Returns:
            New libvirt connection
        """
        target_uri = uri or self.uri
        
        with self._lock:
            if target_uri in self._connections:
                try:
                    self._connections[target_uri].connection.close()
                except:
                    pass
                del self._connections[target_uri]
            
            self.stats['reconnections'] += 1
            return self._create_connection(target_uri)
    
    def close_all_connections(self) -> None:
        """Close all cached connections"""
        with self._lock:
            for conn_info in self._connections.values():
                try:
                    conn_info.connection.close()
                except:
                    pass
            
            self._connections.clear()
            logger.info("Closed all libvirt connections")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        with self._lock:
            active_connections = len(self._connections)
            return {
                **self.stats,
                'active_connections': active_connections,
                'max_connections': self.max_connections
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on connections"""
        with self._lock:
            healthy_connections = 0
            unhealthy_connections = 0
            
            for conn_info in list(self._connections.values()):
                if self._is_connection_valid(conn_info):
                    healthy_connections += 1
                else:
                    unhealthy_connections += 1
                    # Clean up unhealthy connection
                    try:
                        conn_info.connection.close()
                    except:
                        pass
                    del self._connections[conn_info.uri]
            
            return {
                'healthy_connections': healthy_connections,
                'unhealthy_connections': unhealthy_connections,
                'total_managed': len(self._connections),
                'primary_uri': self.uri,
                'libvirt_available': True
            }
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close_all_connections()


# Global connection manager instances for common URIs
_connection_managers: Dict[str, LibvirtConnectionManager] = {}
_manager_lock = threading.Lock()


def get_connection_manager(uri: str = "qemu:///system") -> LibvirtConnectionManager:
    """
    Get or create a connection manager for the given URI.
    
    This function provides a convenient way to get singleton connection managers
    for different URIs, ensuring efficient connection reuse across the application.
    
    Args:
        uri: LibVirt connection URI
        
    Returns:
        Connection manager for the URI
    """
    with _manager_lock:
        if uri not in _connection_managers:
            _connection_managers[uri] = LibvirtConnectionManager(uri)
        return _connection_managers[uri]


def cleanup_all_managers() -> None:
    """Clean up all global connection managers"""
    with _manager_lock:
        for manager in _connection_managers.values():
            manager.close_all_connections()
        _connection_managers.clear()