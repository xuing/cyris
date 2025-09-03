"""
Network Configuration and SSH Connection Reliability

This module provides improved network configuration validation and SSH connection
management with retry policies, connection pooling, and health monitoring.
"""

import socket
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
import ipaddress
import re

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None

from .exceptions import CyRISNetworkError, handle_exception


logger = logging.getLogger(__name__)


@dataclass
class NetworkTestResult:
    """Result of network connectivity test"""
    success: bool
    response_time: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NetworkValidationResult:
    """Result of network configuration validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RetryPolicy:
    """Retry policy for network operations"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        if attempt == 0:
            return 0
        
        delay = self.base_delay * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay)
    
    def should_retry(self, attempt: int) -> bool:
        """Determine if should retry based on attempt number"""
        return attempt < self.max_attempts


class NetworkValidator:
    """Validates network configurations and connectivity"""
    
    def __init__(self):
        """Initialize network validator"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def validate_ip_address(self, ip: Any) -> bool:
        """
        Validate IP address format.
        
        Args:
            ip: IP address to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(ip, str) or not ip:
            return False
        
        try:
            ipaddress.ip_address(ip)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    def validate_network_config(self, config: Dict[str, Any]) -> NetworkValidationResult:
        """
        Validate network configuration dictionary.
        
        Args:
            config: Network configuration to validate
            
        Returns:
            NetworkValidationResult with validation status and errors
        """
        errors = []
        warnings = []
        
        # Validate network mode
        network_mode = config.get("network_mode")
        if network_mode not in ["user", "bridge", None]:
            errors.append(f"Invalid network_mode: {network_mode}. Must be 'user' or 'bridge'")
        
        # Validate bridge configuration
        if network_mode == "bridge":
            bridge_name = config.get("bridge_name")
            if not bridge_name or not isinstance(bridge_name, str):
                errors.append("bridge_name is required for bridge networking")
        
        # Validate IP range if provided
        ip_range = config.get("ip_range")
        if ip_range:
            try:
                ipaddress.ip_network(ip_range, strict=False)
            except (ipaddress.AddressValueError, ValueError):
                errors.append(f"Invalid ip_range format: {ip_range}")
        
        # Validate enable_ssh flag
        enable_ssh = config.get("enable_ssh")
        if enable_ssh is not None and not isinstance(enable_ssh, bool):
            errors.append("enable_ssh must be a boolean value")
        
        # Check for SSH with user mode
        if network_mode == "user" and enable_ssh:
            warnings.append("SSH with user-mode networking may require port forwarding")
        
        return NetworkValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )
    
    def test_port_connectivity(
        self, 
        hostname: str, 
        port: int, 
        timeout: float = 5.0
    ) -> NetworkTestResult:
        """
        Test TCP connectivity to a specific host and port.
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            timeout: Connection timeout in seconds
            
        Returns:
            NetworkTestResult with connectivity status
        """
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((hostname, port))
            response_time = time.time() - start_time
            
            sock.close()
            
            if result == 0:
                return NetworkTestResult(
                    success=True,
                    response_time=response_time
                )
            else:
                return NetworkTestResult(
                    success=False,
                    response_time=response_time,
                    error_message=f"Connection failed with code {result}"
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return NetworkTestResult(
                success=False,
                response_time=response_time,
                error_message=str(e)
            )


class ConnectionPool:
    """Manages pool of SSH connections with lifecycle management"""
    
    def __init__(self, max_connections: int = 10, idle_timeout: int = 300):
        """
        Initialize connection pool.
        
        Args:
            max_connections: Maximum number of connections to maintain
            idle_timeout: Timeout in seconds for idle connections
        """
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        self._connections: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def __len__(self) -> int:
        """Return number of connections in pool"""
        return len(self._connections)
    
    def add_connection(self, hostname: str, connection: Any) -> None:
        """
        Add connection to pool.
        
        Args:
            hostname: Hostname for the connection
            connection: SSH connection object
            
        Raises:
            CyRISNetworkError: If pool is full
        """
        with self._lock:
            if len(self._connections) >= self.max_connections:
                raise CyRISNetworkError(
                    "Connection pool is full",
                    operation="add_connection",
                    additional_data={"max_connections": self.max_connections}
                )
            
            self._connections[hostname] = {
                "connection": connection,
                "created_at": datetime.now(),
                "last_used": datetime.now()
            }
            
            self.logger.debug(f"Added connection for {hostname} to pool")
    
    def get_connection(self, hostname: str) -> Optional[Any]:
        """Get connection from pool and update last used time"""
        with self._lock:
            if hostname in self._connections:
                self._connections[hostname]["last_used"] = datetime.now()
                return self._connections[hostname]["connection"]
            return None
    
    def remove_connection(self, hostname: str) -> bool:
        """Remove connection from pool"""
        with self._lock:
            if hostname in self._connections:
                connection_info = self._connections.pop(hostname)
                try:
                    connection_info["connection"].close()
                except:
                    pass  # Ignore close errors
                self.logger.debug(f"Removed connection for {hostname} from pool")
                return True
            return False
    
    def cleanup_idle_connections(self) -> int:
        """Clean up idle connections that exceed timeout"""
        cleaned_count = 0
        current_time = datetime.now()
        timeout_delta = timedelta(seconds=self.idle_timeout)
        
        with self._lock:
            expired_hosts = []
            for hostname, info in self._connections.items():
                if current_time - info["last_used"] > timeout_delta:
                    expired_hosts.append(hostname)
            
            for hostname in expired_hosts:
                if self.remove_connection(hostname):
                    cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} idle connections")
        
        return cleaned_count
    
    def close_all(self) -> None:
        """Close all connections in the pool"""
        with self._lock:
            hostnames = list(self._connections.keys())
            for hostname in hostnames:
                self.remove_connection(hostname)


class SSHHealthChecker:
    """Monitors SSH connection health"""
    
    def __init__(self, check_interval: int = 60):
        """
        Initialize health checker.
        
        Args:
            check_interval: Interval between health checks in seconds
        """
        self.check_interval = check_interval
        self.is_running = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def check_ssh_health(self, ssh_client: Any) -> bool:
        """
        Check if SSH connection is healthy by running a simple command.
        
        Args:
            ssh_client: SSH client to test
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Execute a simple command to test connectivity
            stdin, stdout, stderr = ssh_client.exec_command("echo 'health_check'", timeout=5)
            result = stdout.read().decode().strip()
            
            return result == "health_check"
            
        except Exception as e:
            self.logger.debug(f"SSH health check failed: {e}")
            return False


class SSHConnectionManager:
    """Enhanced SSH connection manager with reliability features"""
    
    def __init__(
        self, 
        default_timeout: int = 30,
        max_connections: int = 10,
        health_check_interval: int = 60
    ):
        """
        Initialize SSH connection manager.
        
        Args:
            default_timeout: Default connection timeout
            max_connections: Maximum connections in pool
            health_check_interval: Health check interval in seconds
        """
        self.default_timeout = default_timeout
        self.max_connections = max_connections
        self.health_check_interval = health_check_interval
        
        self._connections = ConnectionPool(max_connections)
        self.health_checker = SSHHealthChecker(health_check_interval)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Start health monitoring in background
        self._health_monitor_thread = None
        self._shutdown_event = threading.Event()
    
    def create_connection(
        self,
        hostname: str,
        username: str = "root",
        password: Optional[str] = None,
        private_key_path: Optional[str] = None,
        port: int = 22,
        timeout: Optional[int] = None,
        retry_policy: Optional[RetryPolicy] = None
    ) -> Optional[Any]:
        """
        Create SSH connection with retry policy.
        
        Args:
            hostname: Target hostname
            username: SSH username
            password: SSH password
            private_key_path: Path to private key file
            port: SSH port
            timeout: Connection timeout
            retry_policy: Retry policy for connection attempts
            
        Returns:
            SSH client object or None if failed
        """
        if not PARAMIKO_AVAILABLE:
            self.logger.warning("paramiko not available - SSH connections disabled")
            return None
        
        # Check if connection already exists
        existing = self._connections.get_connection(hostname)
        if existing and self.health_checker.check_ssh_health(existing):
            self.logger.debug(f"Reusing existing healthy connection to {hostname}")
            return existing
        
        # Remove unhealthy connection
        if existing:
            self._connections.remove_connection(hostname)
        
        # Create new connection with retry
        retry_policy = retry_policy or RetryPolicy()
        timeout = timeout or self.default_timeout
        
        for attempt in range(retry_policy.max_attempts):
            try:
                # Add delay for retry attempts
                if attempt > 0:
                    delay = retry_policy.get_delay(attempt)
                    self.logger.debug(f"Retrying connection to {hostname} after {delay}s delay")
                    time.sleep(delay)
                
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect with appropriate authentication
                connect_kwargs = {
                    "hostname": hostname,
                    "port": port,
                    "username": username,
                    "timeout": timeout
                }
                
                if password:
                    connect_kwargs["password"] = password
                elif private_key_path:
                    connect_kwargs["key_filename"] = private_key_path
                else:
                    # Try key-based auth
                    connect_kwargs["look_for_keys"] = True
                    connect_kwargs["allow_agent"] = True
                
                ssh_client.connect(**connect_kwargs)
                
                # Add to pool
                self._connections.add_connection(hostname, ssh_client)
                self.logger.info(f"Successfully connected to {hostname} on attempt {attempt + 1}")
                return ssh_client
                
            except Exception as e:
                self.logger.warning(f"Connection attempt {attempt + 1} to {hostname} failed: {e}")
                if not retry_policy.should_retry(attempt + 1):
                    self.logger.error(f"All connection attempts to {hostname} failed")
                    handle_exception(
                        CyRISNetworkError(
                            f"Failed to connect to {hostname} after {retry_policy.max_attempts} attempts",
                            operation="create_ssh_connection",
                            additional_data={"hostname": hostname, "attempts": attempt + 1}
                        )
                    )
                    break
                
                # Clean up failed client
                try:
                    ssh_client.close()
                except:
                    pass
        
        return None
    
    def get_connection(self, hostname: str) -> Optional[Any]:
        """Get existing connection from pool"""
        return self._connections.get_connection(hostname)
    
    def close_connection(self, hostname: str) -> bool:
        """Close specific connection"""
        return self._connections.remove_connection(hostname)
    
    def close_all_connections(self) -> None:
        """Close all connections"""
        self._connections.close_all()
        self._shutdown_event.set()
        
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            self._health_monitor_thread.join(timeout=5)
    
    def check_connection_health(self, hostname: str) -> bool:
        """Check health of specific connection"""
        connection = self._connections.get_connection(hostname)
        if connection:
            return self.health_checker.check_ssh_health(connection)
        return False
    
    def cleanup_idle_connections(self) -> int:
        """Clean up idle connections"""
        return self._connections.cleanup_idle_connections()
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        with self._connections._lock:
            active_connections = len(self._connections._connections)
            return {
                "active_connections": active_connections,
                "max_connections": self.max_connections,
                "connection_utilization": active_connections / self.max_connections,
                "pool_hosts": list(self._connections._connections.keys())
            }


def validate_ssh_connectivity(hostname: str, port: int = 22, timeout: float = 5.0) -> NetworkTestResult:
    """
    Convenience function to test SSH connectivity.
    
    Args:
        hostname: Target hostname
        port: SSH port (default 22)
        timeout: Connection timeout
        
    Returns:
        NetworkTestResult with connectivity status
    """
    validator = NetworkValidator()
    return validator.test_port_connectivity(hostname, port, timeout)


def create_reliable_ssh_manager(
    max_connections: int = 10,
    default_timeout: int = 30,
    health_check_interval: int = 60
) -> SSHConnectionManager:
    """
    Create SSH connection manager with reliability features.
    
    Args:
        max_connections: Maximum connections in pool
        default_timeout: Default connection timeout
        health_check_interval: Health check interval
        
    Returns:
        Configured SSHConnectionManager instance
    """
    return SSHConnectionManager(
        default_timeout=default_timeout,
        max_connections=max_connections,
        health_check_interval=health_check_interval
    )