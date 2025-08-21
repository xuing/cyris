"""
SSH Reliability Integration

This module enhances the existing SSH manager with network reliability features,
following KISS principle and integrating seamlessly with current SSH operations.
"""

import logging
import time
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from .ssh_manager import SSHManager, SSHCredentials, SSHCommand, SSHResult
from ..core.network_reliability import (
    NetworkValidator, RetryPolicy, NetworkTestResult, 
    validate_ssh_connectivity
)
from ..services.network_service import NetworkService, NetworkServiceConfig
from ..core.exceptions import CyRISNetworkError, handle_exception, safe_execute


logger = logging.getLogger(__name__)


@dataclass
class ReliableSSHConfig:
    """Configuration for reliable SSH operations"""
    enable_network_validation: bool = True
    enable_retry_policy: bool = True
    enable_connection_pooling: bool = True
    enable_health_monitoring: bool = True
    max_retry_attempts: int = 3
    base_retry_delay: float = 1.0
    connection_timeout: int = 30
    health_check_interval: int = 60


class ReliableSSHManager:
    """
    Enhanced SSH manager with reliability features.
    
    Integrates network validation, retry policies, connection pooling,
    and health monitoring with existing SSH management capabilities.
    
    Follows KISS principle by providing simple enhancements to existing SSH operations.
    """
    
    def __init__(
        self, 
        ssh_manager: Optional[SSHManager] = None,
        config: Optional[ReliableSSHConfig] = None,
        network_service: Optional[NetworkService] = None
    ):
        """
        Initialize reliable SSH manager.
        
        Args:
            ssh_manager: Existing SSH manager instance
            config: Reliability configuration
            network_service: Network service for reliability features
        """
        self.ssh_manager = ssh_manager or SSHManager()
        self.config = config or ReliableSSHConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize network service if reliability features are enabled
        if (self.config.enable_network_validation or 
            self.config.enable_connection_pooling):
            
            network_config = NetworkServiceConfig(
                max_ssh_connections=self.ssh_manager.max_connections,
                default_ssh_timeout=self.config.connection_timeout,
                health_check_interval=self.config.health_check_interval,
                enable_connection_pooling=self.config.enable_connection_pooling
            )
            self.network_service = network_service or NetworkService(network_config)
        else:
            self.network_service = None
        
        self.logger.info("ReliableSSHManager initialized")
    
    def validate_network_connectivity(
        self, 
        hostname: str, 
        port: int = 22
    ) -> NetworkTestResult:
        """
        Validate network connectivity before SSH operations.
        
        Args:
            hostname: Target hostname
            port: SSH port
            
        Returns:
            NetworkTestResult with connectivity status
        """
        if not self.config.enable_network_validation:
            return NetworkTestResult(success=True, response_time=0.0)
        
        return safe_execute(
            validate_ssh_connectivity,
            hostname, port, timeout=5.0,
            context={"operation": "validate_connectivity", "hostname": hostname},
            default_return=NetworkTestResult(success=False, error_message="Validation failed"),
            logger=self.logger
        )
    
    def execute_command_with_reliability(
        self,
        credentials: SSHCredentials,
        command: Union[str, SSHCommand],
        retry_policy: Optional[RetryPolicy] = None
    ) -> SSHResult:
        """
        Execute SSH command with reliability enhancements.
        
        Args:
            credentials: SSH connection credentials
            command: Command to execute
            retry_policy: Optional retry policy
            
        Returns:
            SSH execution result
        """
        if isinstance(command, str):
            command = SSHCommand(command, "Execute with reliability")
        
        # Pre-execution network validation
        if self.config.enable_network_validation:
            connectivity = self.validate_network_connectivity(
                credentials.hostname, 
                credentials.port
            )
            
            if not connectivity.success:
                self.logger.warning(
                    f"Network connectivity check failed for {credentials.hostname}: "
                    f"{connectivity.error_message}"
                )
                return SSHResult(
                    hostname=credentials.hostname,
                    command=command.command,
                    return_code=-1,
                    stdout="",
                    stderr=f"Network connectivity failed: {connectivity.error_message}",
                    execution_time=connectivity.response_time,
                    success=False,
                    error_message=connectivity.error_message
                )
        
        # Configure retry policy
        if self.config.enable_retry_policy and retry_policy is None:
            retry_policy = RetryPolicy(
                max_attempts=self.config.max_retry_attempts,
                base_delay=self.config.base_retry_delay
            )
        
        # Execute with retry if enabled
        if retry_policy and self.config.enable_retry_policy:
            return self._execute_with_retry(credentials, command, retry_policy)
        else:
            return self.ssh_manager.execute_command(credentials, command)
    
    def create_connection_with_reliability(
        self,
        credentials: SSHCredentials,
        retry_policy: Optional[RetryPolicy] = None
    ) -> Optional[Any]:
        """
        Create SSH connection with reliability features.
        
        Args:
            credentials: SSH connection credentials
            retry_policy: Optional retry policy
            
        Returns:
            SSH connection object or None if failed
        """
        # Use network service connection pooling if available
        if self.network_service and self.config.enable_connection_pooling:
            return self.network_service.create_ssh_connection(
                hostname=credentials.hostname,
                username=credentials.username,
                password=credentials.password,
                private_key_path=credentials.private_key_path,
                port=credentials.port,
                use_retry=self.config.enable_retry_policy
            )
        
        # Fallback to regular connection creation
        if not self.config.enable_network_validation:
            return self.ssh_manager._get_connection(credentials)
        
        # Pre-connection validation
        connectivity = self.validate_network_connectivity(
            credentials.hostname,
            credentials.port
        )
        
        if not connectivity.success:
            self.logger.error(
                f"Cannot create connection to {credentials.hostname}: "
                f"network validation failed"
            )
            return None
        
        return self.ssh_manager._get_connection(credentials)
    
    def test_connection_with_reliability(
        self, 
        credentials: SSHCredentials
    ) -> bool:
        """
        Test SSH connection with reliability enhancements.
        
        Args:
            credentials: SSH connection credentials
            
        Returns:
            True if connection successful, False otherwise
        """
        # Network validation first
        if self.config.enable_network_validation:
            connectivity = self.validate_network_connectivity(
                credentials.hostname,
                credentials.port
            )
            
            if not connectivity.success:
                self.logger.debug(
                    f"Connection test failed for {credentials.hostname}: "
                    f"network validation failed"
                )
                return False
        
        # Use pooled connection if available
        if self.network_service and self.config.enable_connection_pooling:
            existing_connection = self.network_service.get_ssh_connection(credentials.hostname)
            if existing_connection:
                health_status = self.network_service.check_ssh_health(credentials.hostname)
                if health_status:
                    return True
        
        # Fallback to regular connection test
        return safe_execute(
            self.ssh_manager.test_connection,
            credentials,
            context={"operation": "test_connection", "hostname": credentials.hostname},
            default_return=False,
            logger=self.logger
        )
    
    def get_reliability_stats(self) -> Dict[str, Any]:
        """Get reliability statistics"""
        stats = {
            "config": {
                "network_validation_enabled": self.config.enable_network_validation,
                "retry_policy_enabled": self.config.enable_retry_policy,
                "connection_pooling_enabled": self.config.enable_connection_pooling,
                "health_monitoring_enabled": self.config.enable_health_monitoring,
                "max_retry_attempts": self.config.max_retry_attempts
            },
            "ssh_manager": self.ssh_manager.get_ssh_manager_stats()
        }
        
        if self.network_service:
            stats["network_service"] = self.network_service.get_network_statistics()
        
        return stats
    
    def cleanup(self) -> None:
        """Cleanup reliability resources"""
        if self.network_service:
            self.network_service.shutdown()
        
        self.ssh_manager.close_all_connections()
        self.logger.info("ReliableSSHManager cleanup complete")
    
    def _execute_with_retry(
        self,
        credentials: SSHCredentials,
        command: SSHCommand,
        retry_policy: RetryPolicy
    ) -> SSHResult:
        """Execute command with retry policy"""
        last_result = None
        
        for attempt in range(retry_policy.max_attempts):
            try:
                # Add delay for retry attempts
                if attempt > 0:
                    delay = retry_policy.get_delay(attempt)
                    self.logger.debug(
                        f"Retrying command on {credentials.hostname} "
                        f"after {delay}s delay (attempt {attempt + 1})"
                    )
                    time.sleep(delay)
                
                result = self.ssh_manager.execute_command(credentials, command)
                
                # Command succeeded
                if result.success:
                    if attempt > 0:
                        self.logger.info(
                            f"Command succeeded on {credentials.hostname} "
                            f"on attempt {attempt + 1}"
                        )
                    return result
                
                last_result = result
                
                # Check if we should retry
                if not retry_policy.should_retry(attempt + 1):
                    break
                
                self.logger.warning(
                    f"Command failed on {credentials.hostname} "
                    f"(attempt {attempt + 1}): {result.stderr}"
                )
                
            except Exception as e:
                self.logger.error(
                    f"Command execution error on {credentials.hostname} "
                    f"(attempt {attempt + 1}): {e}"
                )
                
                last_result = SSHResult(
                    hostname=credentials.hostname,
                    command=command.command,
                    return_code=-1,
                    stdout="",
                    stderr=str(e),
                    execution_time=0.0,
                    success=False,
                    error_message=str(e)
                )
                
                if not retry_policy.should_retry(attempt + 1):
                    break
        
        # All attempts failed
        self.logger.error(
            f"All {retry_policy.max_attempts} attempts failed for "
            f"command on {credentials.hostname}"
        )
        
        return last_result or SSHResult(
            hostname=credentials.hostname,
            command=command.command,
            return_code=-1,
            stdout="",
            stderr="All retry attempts failed",
            execution_time=0.0,
            success=False,
            error_message="Maximum retry attempts exceeded"
        )


# Convenience functions for easy adoption
def create_reliable_ssh_manager(
    ssh_manager: Optional[SSHManager] = None,
    enable_all_features: bool = True
) -> ReliableSSHManager:
    """
    Create reliable SSH manager with sensible defaults.
    
    Args:
        ssh_manager: Existing SSH manager to enhance
        enable_all_features: Enable all reliability features
        
    Returns:
        Configured ReliableSSHManager
    """
    if enable_all_features:
        config = ReliableSSHConfig(
            enable_network_validation=True,
            enable_retry_policy=True,
            enable_connection_pooling=True,
            enable_health_monitoring=True
        )
    else:
        config = ReliableSSHConfig(
            enable_network_validation=True,
            enable_retry_policy=True,
            enable_connection_pooling=False,
            enable_health_monitoring=False
        )
    
    return ReliableSSHManager(ssh_manager=ssh_manager, config=config)


def enhance_ssh_credentials_validation(credentials: SSHCredentials) -> bool:
    """
    Validate SSH credentials before connection attempts.
    
    Args:
        credentials: SSH credentials to validate
        
    Returns:
        True if credentials appear valid, False otherwise
    """
    validator = NetworkValidator()
    
    # Basic validation
    if not credentials.hostname:
        return False
    
    if not validator.validate_ip_address(credentials.hostname):
        # Might be hostname, check if it looks reasonable
        if not credentials.hostname.replace('.', '').replace('-', '').replace('_', '').isalnum():
            return False
    
    if not (1 <= credentials.port <= 65535):
        return False
    
    if not credentials.username:
        return False
    
    # Must have some authentication method
    if not any([credentials.password, credentials.private_key_path, credentials.private_key_data]):
        return False
    
    return True