"""
Test network configuration and SSH connection reliability improvements
测试网络配置和SSH连接可靠性改进
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import socket
import time
from concurrent.futures import Future

# Add src to Python path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.core.network_reliability import (
    NetworkValidator, SSHConnectionManager, ConnectionPool,
    NetworkTestResult, SSHHealthChecker, RetryPolicy
)
from cyris.core.exceptions import CyRISNetworkError


class TestNetworkValidator:
    """Test network validation functionality"""
    
    def test_validate_ip_address_valid(self):
        """Test validation of valid IP addresses"""
        validator = NetworkValidator()
        
        valid_ips = [
            "192.168.1.1",
            "10.0.0.1", 
            "172.16.0.1",
            "127.0.0.1"
        ]
        
        for ip in valid_ips:
            assert validator.validate_ip_address(ip) is True
    
    def test_validate_ip_address_invalid(self):
        """Test validation rejects invalid IP addresses"""
        validator = NetworkValidator()
        
        invalid_ips = [
            "256.1.1.1",  # Out of range
            "192.168.1",  # Incomplete
            "192.168.1.1.1",  # Too many octets
            "not.an.ip.address",  # Non-numeric
            "",  # Empty
            None  # None
        ]
        
        for ip in invalid_ips:
            assert validator.validate_ip_address(ip) is False
    
    def test_validate_network_configuration(self):
        """Test network configuration validation"""
        validator = NetworkValidator()
        
        # Valid configuration
        valid_config = {
            "network_mode": "bridge",
            "bridge_name": "virbr0", 
            "ip_range": "192.168.100.0/24",
            "enable_ssh": True
        }
        
        result = validator.validate_network_config(valid_config)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_network_configuration_invalid(self):
        """Test network configuration validation with errors"""
        validator = NetworkValidator()
        
        # Invalid configuration
        invalid_config = {
            "network_mode": "invalid_mode",
            "bridge_name": "",
            "ip_range": "invalid.range",
            "enable_ssh": "not_boolean"
        }
        
        result = validator.validate_network_config(invalid_config)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "network_mode" in str(result.errors)
    
    @patch('socket.socket')
    def test_test_port_connectivity_success(self, mock_socket):
        """Test successful port connectivity check"""
        validator = NetworkValidator()
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 0  # Success
        
        result = validator.test_port_connectivity("192.168.1.1", 22)
        
        assert result.success is True
        assert result.response_time > 0
        mock_sock.settimeout.assert_called_once()
        mock_sock.connect_ex.assert_called_once_with(("192.168.1.1", 22))
    
    @patch('socket.socket')
    def test_test_port_connectivity_failure(self, mock_socket):
        """Test failed port connectivity check"""
        validator = NetworkValidator()
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 1  # Connection refused
        
        result = validator.test_port_connectivity("192.168.1.1", 22)
        
        assert result.success is False
        assert result.error_message is not None


class TestRetryPolicy:
    """Test retry policy functionality"""
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff timing calculation"""
        policy = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            backoff_multiplier=2.0
        )
        
        # First attempt - no delay
        assert policy.get_delay(0) == 0
        
        # Second attempt - base delay 
        assert policy.get_delay(1) == 1.0
        
        # Third attempt - exponential backoff
        assert policy.get_delay(2) == 2.0
        
        # Test max delay limit
        assert policy.get_delay(10) <= 10.0
    
    def test_should_retry_logic(self):
        """Test retry decision logic"""
        policy = RetryPolicy(max_attempts=3)
        
        # Should retry within attempts limit
        assert policy.should_retry(0) is True
        assert policy.should_retry(1) is True
        assert policy.should_retry(2) is True
        
        # Should not retry after max attempts
        assert policy.should_retry(3) is False
        assert policy.should_retry(10) is False


class TestSSHConnectionManager:
    """Test SSH connection management with reliability improvements"""
    
    @pytest.fixture
    def ssh_manager(self):
        """Create SSH connection manager for testing"""
        return SSHConnectionManager(
            default_timeout=10,
            max_connections=5,
            health_check_interval=30
        )
    
    def test_connection_manager_initialization(self, ssh_manager):
        """Test SSH connection manager initialization"""
        assert ssh_manager.default_timeout == 10
        assert ssh_manager.max_connections == 5
        assert ssh_manager.health_check_interval == 30
        assert len(ssh_manager._connections) == 0
    
    @patch('paramiko.SSHClient')
    def test_create_connection_success(self, mock_ssh_client, ssh_manager):
        """Test successful SSH connection creation"""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        
        connection = ssh_manager.create_connection(
            hostname="192.168.1.1",
            username="root",
            password="password"
        )
        
        assert connection is not None
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_create_connection_with_retry(self, mock_ssh_client, ssh_manager):
        """Test SSH connection creation with retry on failure"""
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        
        # First attempt fails, second succeeds
        mock_client.connect.side_effect = [
            Exception("Connection failed"),
            None  # Success
        ]
        
        connection = ssh_manager.create_connection(
            hostname="192.168.1.1",
            username="root", 
            password="password",
            retry_policy=RetryPolicy(max_attempts=2)
        )
        
        assert connection is not None
        assert mock_client.connect.call_count == 2
    
    def test_connection_pooling(self, ssh_manager):
        """Test connection pooling functionality"""
        with patch('paramiko.SSHClient') as mock_ssh_client:
            mock_client = Mock()
            mock_ssh_client.return_value = mock_client
            
            # Create first connection
            conn1 = ssh_manager.create_connection(
                hostname="192.168.1.1",
                username="root"
            )
            
            # Create second connection to same host - should reuse
            conn2 = ssh_manager.get_connection("192.168.1.1")
            
            assert conn1 is conn2  # Should be same connection
            assert len(ssh_manager._connections) == 1
    
    def test_connection_health_monitoring(self, ssh_manager):
        """Test connection health monitoring"""
        with patch('paramiko.SSHClient') as mock_ssh_client:
            mock_client = Mock()
            mock_ssh_client.return_value = mock_client
            
            # Create connection
            ssh_manager.create_connection(
                hostname="192.168.1.1",
                username="root"
            )
            
            # Mock healthy connection - need to properly mock stdout
            mock_stdout = Mock()
            mock_stdout.read.return_value = b"health_check"
            mock_client.exec_command.return_value = (None, mock_stdout, Mock())
            
            # Test health check
            is_healthy = ssh_manager.check_connection_health("192.168.1.1")
            assert is_healthy is True
    
    def test_connection_cleanup(self, ssh_manager):
        """Test connection cleanup functionality"""
        with patch('paramiko.SSHClient') as mock_ssh_client:
            mock_client = Mock()
            mock_ssh_client.return_value = mock_client
            
            # Create connection
            ssh_manager.create_connection(
                hostname="192.168.1.1",
                username="root"
            )
            
            assert len(ssh_manager._connections) == 1
            
            # Close connection
            ssh_manager.close_connection("192.168.1.1")
            
            assert len(ssh_manager._connections) == 0
            mock_client.close.assert_called_once()


class TestSSHHealthChecker:
    """Test SSH connection health checking"""
    
    def test_health_checker_initialization(self):
        """Test health checker initialization"""
        checker = SSHHealthChecker(check_interval=30)
        
        assert checker.check_interval == 30
        assert checker.is_running is False
    
    def test_health_check_command_execution(self):
        """Test health check command execution"""
        checker = SSHHealthChecker()
        
        mock_client = Mock()
        mock_stdout = Mock()
        mock_stdout.read.return_value = b"health_check"  # Must match expected response
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)
        
        result = checker.check_ssh_health(mock_client)
        
        assert result is True
        mock_client.exec_command.assert_called_once()
    
    def test_health_check_failure_detection(self):
        """Test health check failure detection"""
        checker = SSHHealthChecker()
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_client.exec_command.side_effect = Exception("SSH command failed")
            
            result = checker.check_ssh_health(mock_client)
            
            assert result is False


class TestConnectionPool:
    """Test connection pool management"""
    
    def test_connection_pool_initialization(self):
        """Test connection pool initialization"""
        pool = ConnectionPool(max_connections=10, idle_timeout=300)
        
        assert pool.max_connections == 10
        assert pool.idle_timeout == 300
        assert len(pool._connections) == 0
    
    def test_connection_pool_limit_enforcement(self):
        """Test connection pool enforces maximum connections"""
        pool = ConnectionPool(max_connections=2)
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            
            # Add connections up to limit
            pool.add_connection("host1", mock_client)
            pool.add_connection("host2", mock_client)
            
            assert len(pool._connections) == 2
            
            # Adding beyond limit should raise error
            with pytest.raises(CyRISNetworkError, match="Connection pool is full"):
                pool.add_connection("host3", mock_client)
    
    def test_idle_connection_cleanup(self):
        """Test cleanup of idle connections"""
        pool = ConnectionPool(idle_timeout=1)  # 1 second timeout
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            
            # Add connection
            pool.add_connection("host1", mock_client)
            assert len(pool._connections) == 1
            
            # Wait for timeout
            time.sleep(1.1)
            
            # Cleanup should remove idle connection
            pool.cleanup_idle_connections()
            assert len(pool._connections) == 0
            mock_client.close.assert_called_once()


class TestNetworkReliabilityIntegration:
    """Integration tests for network reliability features"""
    
    def test_end_to_end_ssh_connection_with_retry(self):
        """Test end-to-end SSH connection with retry mechanism"""
        manager = SSHConnectionManager()
        validator = NetworkValidator()
        
        # Test network connectivity first
        connectivity = validator.test_port_connectivity("127.0.0.1", 22, timeout=5)
        
        if connectivity.success:
            # Attempt SSH connection with retry
            with patch('paramiko.SSHClient') as mock_ssh:
                mock_client = Mock()
                mock_ssh.return_value = mock_client
                
                connection = manager.create_connection(
                    hostname="127.0.0.1",
                    username="test",
                    retry_policy=RetryPolicy(max_attempts=3)
                )
                
                assert connection is not None
        else:
            # Skip if SSH not available on localhost
            pytest.skip("SSH service not available for testing")
    
    def test_network_configuration_validation_integration(self):
        """Test integrated network configuration validation"""
        validator = NetworkValidator()
        
        # Test various network configurations
        configurations = [
            {
                "network_mode": "user",
                "enable_ssh": False,
                "description": "Isolated user networking"
            },
            {
                "network_mode": "bridge", 
                "bridge_name": "virbr0",
                "enable_ssh": True,
                "ip_range": "192.168.100.0/24",
                "description": "Bridge networking with SSH"
            }
        ]
        
        for config in configurations:
            result = validator.validate_network_config(config)
            assert result.is_valid is True, f"Configuration should be valid: {config['description']}"


@pytest.fixture
def temp_dir(tmp_path):
    """Temporary directory fixture for tests"""
    return tmp_path