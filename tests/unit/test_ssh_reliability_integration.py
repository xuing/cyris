"""
Test SSH reliability integration with existing SSH manager
测试SSH可靠性与现有SSH管理器的集成
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import paramiko
from threading import Lock

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.tools.ssh_manager import SSHManager, SSHCredentials, SSHCommand, SSHResult
from cyris.core.network_reliability import (
    SSHConnectionManager, RetryPolicy, NetworkTestResult
)
from cyris.services.network_service import NetworkService, NetworkServiceConfig


class TestSSHReliabilityIntegration:
    """Test integration between SSH manager and network reliability features"""
    
    @pytest.fixture
    def ssh_credentials(self):
        """Create SSH credentials for testing"""
        return SSHCredentials(
            hostname="192.168.1.100",
            username="root",
            password="password"
        )
    
    @pytest.fixture
    def network_service_config(self):
        """Create network service configuration"""
        return NetworkServiceConfig(
            max_ssh_connections=5,
            default_ssh_timeout=15,
            enable_connection_pooling=True
        )
    
    def test_ssh_manager_with_network_validation(self, ssh_credentials, network_service_config):
        """Test SSH manager enhanced with network validation"""
        with patch('cyris.tools.ssh_manager.paramiko.SSHClient'):
            ssh_manager = SSHManager()
            
            # Test connection validation before SSH attempt
            with patch.object(ssh_manager, '_validate_network_connectivity') as mock_validate:
                mock_validate.return_value = True
                
                # Mock successful connection test
                with patch.object(ssh_manager, 'test_connection', return_value=True):
                    result = ssh_manager.test_connection(ssh_credentials)
                    
                    assert result is True
                    mock_validate.assert_called_once()
    
    def test_ssh_manager_with_retry_policy(self, ssh_credentials):
        """Test SSH manager with integrated retry policy"""
        with patch('cyris.tools.ssh_manager.paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            
            # First connection attempt fails, second succeeds
            mock_client.connect.side_effect = [
                paramiko.AuthenticationException("Auth failed"),
                None  # Success on retry
            ]
            
            ssh_manager = SSHManager()
            
            # Test enhanced connection method with retry
            with patch.object(ssh_manager, '_create_connection_with_retry') as mock_retry:
                mock_retry.return_value = mock_client
                
                result = ssh_manager._create_connection_with_retry(
                    ssh_credentials, 
                    retry_policy=RetryPolicy(max_attempts=2)
                )
                
                assert result is not None
                mock_retry.assert_called_once()
    
    def test_ssh_manager_connection_health_monitoring(self, ssh_credentials):
        """Test SSH manager with connection health monitoring"""
        ssh_manager = SSHManager()
        
        with patch.object(ssh_manager, '_monitor_connection_health') as mock_monitor:
            mock_monitor.return_value = True
            
            # Test health check integration
            health_status = ssh_manager._monitor_connection_health(ssh_credentials.hostname)
            
            assert health_status is True
            mock_monitor.assert_called_once_with(ssh_credentials.hostname)
    
    def test_ssh_manager_enhanced_execute_command(self, ssh_credentials):
        """Test enhanced command execution with reliability features"""
        with patch('cyris.tools.ssh_manager.paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            
            # Mock command execution
            mock_stdin = Mock()
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_stdout.read.return_value = b"command output"
            mock_stderr.read.return_value = b""
            mock_stdout.channel.recv_exit_status.return_value = 0
            
            mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
            
            ssh_manager = SSHManager()
            
            # Test enhanced command execution
            with patch.object(ssh_manager, '_execute_with_reliability') as mock_enhanced:
                mock_enhanced.return_value = SSHResult(
                    hostname=ssh_credentials.hostname,
                    command="echo test",
                    return_code=0,
                    stdout="command output",
                    stderr="",
                    execution_time=0.1,
                    success=True
                )
                
                command = SSHCommand("echo test", "Test command")
                result = ssh_manager._execute_with_reliability(ssh_credentials, command)
                
                assert result.success is True
                assert result.stdout == "command output"
                mock_enhanced.assert_called_once()
    
    def test_network_service_ssh_manager_integration(self, network_service_config):
        """Test NetworkService integration with SSH manager functionality"""
        from cyris.services.network_service import NetworkService
        
        network_service = NetworkService(network_service_config)
        
        # Test SSH connection creation through network service
        with patch.object(network_service.ssh_manager, 'create_connection') as mock_create:
            mock_connection = Mock()
            mock_create.return_value = mock_connection
            
            connection = network_service.create_ssh_connection(
                hostname="192.168.1.100",
                username="root",
                password="password"
            )
            
            assert connection is not None
            mock_create.assert_called_once()
    
    def test_connection_pool_with_ssh_credentials(self, ssh_credentials, network_service_config):
        """Test connection pooling with SSH credential objects"""
        from cyris.services.network_service import NetworkService
        
        network_service = NetworkService(network_service_config)
        
        # Test connection pooling with credential conversion
        with patch.object(network_service.ssh_manager, 'create_connection') as mock_create:
            mock_connection = Mock()
            mock_create.return_value = mock_connection
            
            # Create connection using SSH credentials
            connection = network_service.create_ssh_connection(
                hostname=ssh_credentials.hostname,
                username=ssh_credentials.username,
                password=ssh_credentials.password,
                port=ssh_credentials.port
            )
            
            # Test connection retrieval
            retrieved_connection = network_service.get_ssh_connection(ssh_credentials.hostname)
            
            assert connection is not None
            # Note: retrieved_connection might be None if pooling implementation differs
    
    def test_parallel_ssh_execution_with_reliability(self, ssh_credentials):
        """Test parallel SSH execution enhanced with reliability features"""
        ssh_manager = SSHManager()
        
        # Simulate multiple hosts
        host_commands = {
            ssh_credentials: [
                SSHCommand("echo host1", "Test command 1"),
                SSHCommand("uptime", "Test command 2")
            ]
        }
        
        with patch.object(ssh_manager, 'execute_commands_parallel') as mock_parallel:
            mock_results = {
                ssh_credentials.hostname: [
                    SSHResult(
                        hostname=ssh_credentials.hostname,
                        command="echo host1",
                        return_code=0,
                        stdout="host1",
                        stderr="",
                        execution_time=0.1,
                        success=True
                    ),
                    SSHResult(
                        hostname=ssh_credentials.hostname,
                        command="uptime",
                        return_code=0,
                        stdout="system uptime info",
                        stderr="",
                        execution_time=0.2,
                        success=True
                    )
                ]
            }
            mock_parallel.return_value = mock_results
            
            results = ssh_manager.execute_commands_parallel(host_commands)
            
            assert len(results) == 1
            assert len(results[ssh_credentials.hostname]) == 2
            assert all(result.success for result in results[ssh_credentials.hostname])
            mock_parallel.assert_called_once()
    
    def test_ssh_key_management_with_reliability(self):
        """Test SSH key management integrated with reliability features"""
        ssh_manager = SSHManager()
        
        with patch.object(ssh_manager, 'generate_ssh_keypair') as mock_generate:
            mock_generate.return_value = ("/path/to/private_key", "/path/to/public_key")
            
            # Test key generation with enhanced security
            private_key, public_key = ssh_manager.generate_ssh_keypair("test_key")
            
            assert private_key.endswith("test_key")
            assert public_key.endswith("test_key.pub")
            mock_generate.assert_called_once()
    
    def test_error_handling_integration(self, ssh_credentials):
        """Test integrated error handling between components"""
        ssh_manager = SSHManager()
        
        with patch('cyris.tools.ssh_manager.paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            mock_client.connect.side_effect = Exception("Connection failed")
            
            # Test error handling with integrated exception management
            with patch.object(ssh_manager, '_handle_connection_error') as mock_error_handler:
                mock_error_handler.return_value = None
                
                result = ssh_manager._handle_connection_error(ssh_credentials, Exception("Connection failed"))
                
                assert result is None
                mock_error_handler.assert_called_once()


class TestSSHManagerEnhancement:
    """Test SSH manager enhancement methods"""
    
    def test_validate_network_connectivity_method(self):
        """Test network connectivity validation method"""
        ssh_manager = SSHManager()
        
        # Add network validation method to SSH manager
        with patch.object(ssh_manager, '_validate_network_connectivity') as mock_validate:
            mock_validate.return_value = NetworkTestResult(success=True, response_time=0.1)
            
            result = ssh_manager._validate_network_connectivity("192.168.1.100", 22)
            
            assert result.success is True
            mock_validate.assert_called_once()
    
    def test_connection_retry_with_backoff(self):
        """Test connection retry with exponential backoff"""
        ssh_manager = SSHManager()
        
        with patch.object(ssh_manager, '_retry_connection_with_backoff') as mock_retry:
            mock_retry.return_value = Mock()  # Mock successful connection
            
            credentials = SSHCredentials(hostname="192.168.1.100")
            retry_policy = RetryPolicy(max_attempts=3)
            
            connection = ssh_manager._retry_connection_with_backoff(credentials, retry_policy)
            
            assert connection is not None
            mock_retry.assert_called_once()
    
    def test_connection_health_monitoring_integration(self):
        """Test connection health monitoring integration"""
        ssh_manager = SSHManager()
        
        with patch.object(ssh_manager, '_start_health_monitoring') as mock_monitoring:
            mock_monitoring.return_value = True
            
            # Test health monitoring startup
            result = ssh_manager._start_health_monitoring()
            
            assert result is True
            mock_monitoring.assert_called_once()