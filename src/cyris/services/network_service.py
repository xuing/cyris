"""
Network Service Integration

Simple service to integrate network reliability improvements with CyRIS system.
Follows KISS principle - provides only essential network management functionality.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..core.network_reliability import (
    NetworkValidator, SSHConnectionManager, validate_ssh_connectivity,
    NetworkValidationResult, NetworkTestResult, RetryPolicy
)
from ..core.exceptions import CyRISNetworkError, handle_exception, safe_execute


logger = logging.getLogger(__name__)


@dataclass
class NetworkServiceConfig:
    """Configuration for network service"""
    max_ssh_connections: int = 10
    default_ssh_timeout: int = 30
    health_check_interval: int = 60
    enable_connection_pooling: bool = True


class NetworkService:
    """
    Network service providing reliable connectivity and validation.
    
    Simple integration point for network reliability features following KISS principle.
    """
    
    def __init__(self, config: Optional[NetworkServiceConfig] = None):
        """
        Initialize network service.
        
        Args:
            config: Network service configuration
        """
        self.config = config or NetworkServiceConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.validator = NetworkValidator()
        
        if self.config.enable_connection_pooling:
            self.ssh_manager = SSHConnectionManager(
                default_timeout=self.config.default_ssh_timeout,
                max_connections=self.config.max_ssh_connections,
                health_check_interval=self.config.health_check_interval
            )
        else:
            self.ssh_manager = None
        
        self.logger.info("NetworkService initialized")
    
    def validate_network_configuration(self, config: Dict[str, Any]) -> NetworkValidationResult:
        """
        Validate network configuration.
        
        Args:
            config: Network configuration to validate
            
        Returns:
            NetworkValidationResult with validation status
        """
        try:
            return self.validator.validate_network_config(config)
        except Exception as e:
            handle_exception(e, context={"operation": "validate_network_config"})
            return NetworkValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {str(e)}"]
            )
    
    def test_ssh_connectivity(self, hostname: str, port: int = 22, timeout: float = 5.0) -> NetworkTestResult:
        """
        Test SSH connectivity to a host.
        
        Args:
            hostname: Target hostname
            port: SSH port
            timeout: Connection timeout
            
        Returns:
            NetworkTestResult with connectivity status
        """
        return safe_execute(
            validate_ssh_connectivity,
            hostname, port, timeout,
            context={"operation": "test_ssh_connectivity", "hostname": hostname},
            default_return=NetworkTestResult(success=False, error_message="Test failed"),
            logger=self.logger
        )
    
    def create_ssh_connection(
        self,
        hostname: str,
        username: str = "root",
        password: Optional[str] = None,
        private_key_path: Optional[str] = None,
        port: int = 22,
        use_retry: bool = True
    ) -> Optional[Any]:
        """
        Create SSH connection with reliability features.
        
        Args:
            hostname: Target hostname
            username: SSH username  
            password: SSH password
            private_key_path: Path to private key
            port: SSH port
            use_retry: Whether to use retry policy
            
        Returns:
            SSH connection object or None if failed
        """
        if not self.ssh_manager:
            self.logger.warning("SSH connection pooling disabled")
            return None
        
        retry_policy = RetryPolicy(max_attempts=3) if use_retry else None
        
        return safe_execute(
            self.ssh_manager.create_connection,
            hostname=hostname,
            username=username,
            password=password,
            private_key_path=private_key_path,
            port=port,
            retry_policy=retry_policy,
            context={"operation": "create_ssh_connection", "hostname": hostname},
            default_return=None,
            logger=self.logger
        )
    
    def get_ssh_connection(self, hostname: str) -> Optional[Any]:
        """Get existing SSH connection from pool"""
        if not self.ssh_manager:
            return None
        return self.ssh_manager.get_connection(hostname)
    
    def check_ssh_health(self, hostname: str) -> bool:
        """Check health of SSH connection"""
        if not self.ssh_manager:
            return False
        return self.ssh_manager.check_connection_health(hostname)
    
    def cleanup_ssh_connections(self) -> None:
        """Clean up all SSH connections"""
        if self.ssh_manager:
            self.ssh_manager.close_all_connections()
            self.logger.info("SSH connections cleaned up")
    
    def get_network_statistics(self) -> Dict[str, Any]:
        """Get network service statistics"""
        stats = {
            "config": {
                "max_ssh_connections": self.config.max_ssh_connections,
                "pooling_enabled": self.config.enable_connection_pooling,
                "default_timeout": self.config.default_ssh_timeout
            }
        }
        
        if self.ssh_manager:
            stats["ssh_connections"] = self.ssh_manager.get_connection_stats()
        else:
            stats["ssh_connections"] = {"status": "disabled"}
        
        return stats
    
    def shutdown(self) -> None:
        """Shutdown network service and cleanup resources"""
        self.cleanup_ssh_connections()
        self.logger.info("NetworkService shutdown complete")


# Convenience functions for simple usage
def validate_network_config(config: Dict[str, Any]) -> NetworkValidationResult:
    """Validate network configuration (convenience function)"""
    validator = NetworkValidator()
    return validator.validate_network_config(config)


def check_host_connectivity(hostname: str, port: int = 22) -> bool:
    """Check if host is reachable on given port (convenience function)"""
    result = validate_ssh_connectivity(hostname, port, timeout=5.0)
    return result.success