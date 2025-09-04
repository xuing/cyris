"""
Simple LibVirt Connection Manager

Simplified version without external dependencies, focusing on core functionality.
"""

import libvirt
import threading
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

logger = get_logger(__name__, "libvirt_connection_manager_simple")


class SimpleLibvirtConnectionError(Exception):
    """Exception raised for libvirt connection errors"""
    pass


class SimpleLibvirtDomainError(Exception):
    """Exception raised for domain operation errors"""
    pass


class ConnectionInfo:
    """Simple connection information"""
    def __init__(self, uri: str, connection: libvirt.virConnect):
        self.uri = uri
        self.connection = connection
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.use_count = 0
    
    def update_usage(self):
        self.last_used = datetime.now()
        self.use_count += 1


class SimpleLibvirtConnectionManager:
    """Simplified LibVirt connection manager"""
    
    def __init__(self, uri: str = "qemu:///system", timeout: int = 30):
        self.uri = uri
        self.timeout = timeout
        self.logger = logger
        
        # Simple connection pool
        self._connections: Dict[str, ConnectionInfo] = {}
        self._lock = threading.RLock()
        
        # Test initial connection
        self._test_connection()
    
    def _test_connection(self):
        """Test initial connection"""
        try:
            test_conn = libvirt.open(self.uri)
            if test_conn is None:
                raise SimpleLibvirtConnectionError(f"Failed to connect to {self.uri}")
            
            hostname = test_conn.getHostname()
            self.logger.info(f"Connected to libvirt: {hostname} ({self.uri})")
            test_conn.close()
            
        except libvirt.libvirtError as e:
            self.logger.error(f"LibVirt connection test failed: {e}")
            raise SimpleLibvirtConnectionError(f"LibVirt not available: {e}")
    
    def get_connection(self, uri: Optional[str] = None) -> libvirt.virConnect:
        """Get a libvirt connection"""
        target_uri = uri or self.uri
        
        with self._lock:
            # Try to reuse existing connection
            if target_uri in self._connections:
                conn_info = self._connections[target_uri]
                try:
                    # Test if connection is still alive
                    conn_info.connection.getHostname()
                    conn_info.update_usage()
                    return conn_info.connection
                except:
                    # Connection is dead, remove it
                    del self._connections[target_uri]
            
            # Create new connection
            return self._create_connection(target_uri)
    
    def _create_connection(self, uri: str) -> libvirt.virConnect:
        """Create new libvirt connection"""
        try:
            conn = libvirt.open(uri)
            if conn is None:
                raise SimpleLibvirtConnectionError(f"Failed to connect to {uri}")
            
            conn_info = ConnectionInfo(uri, conn)
            self._connections[uri] = conn_info
            
            self.logger.debug(f"Created new libvirt connection: {uri}")
            return conn
            
        except libvirt.libvirtError as e:
            self.logger.error(f"Failed to create libvirt connection to {uri}: {e}")
            raise SimpleLibvirtConnectionError(f"Connection failed: {e}")
    
    def get_domain(self, domain_name: str, uri: Optional[str] = None) -> libvirt.virDomain:
        """Get domain by name"""
        try:
            conn = self.get_connection(uri)
            domain = conn.lookupByName(domain_name)
            return domain
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                raise SimpleLibvirtDomainError(f"Domain not found: {domain_name}")
            else:
                raise SimpleLibvirtDomainError(f"Failed to lookup domain {domain_name}: {e}")
    
    def list_domains(self, active_only: bool = False, uri: Optional[str] = None) -> List[libvirt.virDomain]:
        """List domains"""
        try:
            conn = self.get_connection(uri)
            if active_only:
                domain_ids = conn.listDomainsID()
                domains = [conn.lookupByID(domain_id) for domain_id in domain_ids]
            else:
                domains = conn.listAllDomains()
            return domains
        except libvirt.libvirtError as e:
            self.logger.error(f"Failed to list domains: {e}")
            return []
    
    def close_all_connections(self):
        """Close all cached connections"""
        with self._lock:
            for conn_info in self._connections.values():
                try:
                    conn_info.connection.close()
                except:
                    pass
            self._connections.clear()
            self.logger.info("Closed all libvirt connections")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all_connections()


# Global connection manager
_connection_managers: Dict[str, SimpleLibvirtConnectionManager] = {}
_manager_lock = threading.Lock()


def get_simple_connection_manager(uri: str = "qemu:///system") -> SimpleLibvirtConnectionManager:
    """Get or create a connection manager"""
    with _manager_lock:
        if uri not in _connection_managers:
            _connection_managers[uri] = SimpleLibvirtConnectionManager(uri)
        return _connection_managers[uri]