"""
Test SSH reliability integration - simplified version
测试SSH可靠性集成 - 简化版本
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.tools.ssh_manager import SSHManager, SSHCredentials, SSHCommand
from cyris.tools.ssh_reliability_integration import (
    ReliableSSHManager, ReliableSSHConfig, create_reliable_ssh_manager,
    enhance_ssh_credentials_validation
)
from cyris.core.network_reliability import RetryPolicy, NetworkTestResult


class TestReliableSSHManager:
    """Test ReliableSSHManager functionality"""
    
    @pytest.fixture
    def ssh_credentials(self):
        """Create SSH credentials for testing"""
        return SSHCredentials(
            hostname="192.168.1.100",
            username="root",
            password="password"
        )
    
    @pytest.fixture
    def reliable_config(self):
        """Create reliable SSH configuration"""
        return ReliableSSHConfig(
            enable_network_validation=True,
            enable_retry_policy=True,
            enable_connection_pooling=False,  # Disable for simpler testing
            max_retry_attempts=2
        )
    
    def test_reliable_ssh_manager_initialization(self, reliable_config):
        """Test ReliableSSHManager initialization"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        assert reliable_manager.config.enable_network_validation is True
        assert reliable_manager.config.enable_retry_policy is True
        assert reliable_manager.config.max_retry_attempts == 2
        assert reliable_manager.ssh_manager is not None
    
    def test_network_validation_enabled(self, ssh_credentials, reliable_config):
        """Test network connectivity validation when enabled"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        with patch('cyris.tools.ssh_reliability_integration.validate_ssh_connectivity') as mock_validate:
            mock_validate.return_value = NetworkTestResult(success=True, response_time=0.1)
            
            result = reliable_manager.validate_network_connectivity(
                ssh_credentials.hostname,
                ssh_credentials.port
            )
            
            assert result.success is True
            mock_validate.assert_called_once()
    
    def test_network_validation_disabled(self, ssh_credentials):
        """Test network validation when disabled"""
        config = ReliableSSHConfig(enable_network_validation=False)
        reliable_manager = ReliableSSHManager(config=config)
        
        result = reliable_manager.validate_network_connectivity(
            ssh_credentials.hostname,
            ssh_credentials.port
        )
        
        # Should return success immediately when disabled
        assert result.success is True
        assert result.response_time == 0.0
    
    def test_execute_command_with_network_validation_success(self, ssh_credentials, reliable_config):
        """Test command execution with successful network validation"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        with patch.object(reliable_manager, 'validate_network_connectivity') as mock_validate:
            mock_validate.return_value = NetworkTestResult(success=True, response_time=0.1)
            
            with patch.object(reliable_manager.ssh_manager, 'execute_command') as mock_execute:
                from cyris.tools.ssh_manager import SSHResult
                mock_result = SSHResult(
                    hostname=ssh_credentials.hostname,
                    command="echo test",
                    return_code=0,
                    stdout="test",
                    stderr="",
                    execution_time=0.1,
                    success=True
                )
                mock_execute.return_value = mock_result
                
                result = reliable_manager.execute_command_with_reliability(
                    ssh_credentials,
                    "echo test"
                )
                
                assert result.success is True
                assert result.stdout == "test"
                mock_validate.assert_called_once()
                mock_execute.assert_called_once()
    
    def test_execute_command_with_network_validation_failure(self, ssh_credentials, reliable_config):
        """Test command execution with failed network validation"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        with patch.object(reliable_manager, 'validate_network_connectivity') as mock_validate:
            mock_validate.return_value = NetworkTestResult(
                success=False, 
                error_message="Connection refused",
                response_time=1.0
            )
            
            result = reliable_manager.execute_command_with_reliability(
                ssh_credentials,
                "echo test"
            )
            
            assert result.success is False
            assert "Network connectivity failed" in result.stderr
            mock_validate.assert_called_once()
    
    def test_test_connection_with_reliability(self, ssh_credentials, reliable_config):
        """Test connection testing with reliability features"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        with patch.object(reliable_manager, 'validate_network_connectivity') as mock_validate:
            mock_validate.return_value = NetworkTestResult(success=True)
            
            with patch.object(reliable_manager.ssh_manager, 'test_connection') as mock_test:
                mock_test.return_value = True
                
                result = reliable_manager.test_connection_with_reliability(ssh_credentials)
                
                assert result is True
                mock_validate.assert_called_once()
                mock_test.assert_called_once()
    
    def test_get_reliability_stats(self, reliable_config):
        """Test reliability statistics collection"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        with patch.object(reliable_manager.ssh_manager, 'get_ssh_manager_stats') as mock_stats:
            mock_stats.return_value = {"active_connections": 0}
            
            stats = reliable_manager.get_reliability_stats()
            
            assert "config" in stats
            assert "ssh_manager" in stats
            assert stats["config"]["network_validation_enabled"] is True
            assert stats["config"]["retry_policy_enabled"] is True
    
    def test_cleanup(self, reliable_config):
        """Test cleanup functionality"""
        reliable_manager = ReliableSSHManager(config=reliable_config)
        
        with patch.object(reliable_manager.ssh_manager, 'close_all_connections') as mock_close:
            reliable_manager.cleanup()
            
            mock_close.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_create_reliable_ssh_manager_all_features(self):
        """Test creating reliable SSH manager with all features"""
        reliable_manager = create_reliable_ssh_manager(enable_all_features=True)
        
        assert reliable_manager.config.enable_network_validation is True
        assert reliable_manager.config.enable_retry_policy is True
        assert reliable_manager.config.enable_connection_pooling is True
        assert reliable_manager.config.enable_health_monitoring is True
    
    def test_create_reliable_ssh_manager_minimal_features(self):
        """Test creating reliable SSH manager with minimal features"""
        reliable_manager = create_reliable_ssh_manager(enable_all_features=False)
        
        assert reliable_manager.config.enable_network_validation is True
        assert reliable_manager.config.enable_retry_policy is True
        assert reliable_manager.config.enable_connection_pooling is False
        assert reliable_manager.config.enable_health_monitoring is False
    
    def test_enhance_ssh_credentials_validation_valid(self):
        """Test SSH credentials validation for valid credentials"""
        credentials = SSHCredentials(
            hostname="192.168.1.100",
            username="root",
            password="password",
            port=22
        )
        
        result = enhance_ssh_credentials_validation(credentials)
        assert result is True
    
    def test_enhance_ssh_credentials_validation_invalid_hostname(self):
        """Test SSH credentials validation for invalid hostname"""
        credentials = SSHCredentials(
            hostname="",
            username="root",
            password="password"
        )
        
        result = enhance_ssh_credentials_validation(credentials)
        assert result is False
    
    def test_enhance_ssh_credentials_validation_invalid_port(self):
        """Test SSH credentials validation for invalid port"""
        credentials = SSHCredentials(
            hostname="192.168.1.100",
            username="root",
            password="password",
            port=70000  # Invalid port
        )
        
        result = enhance_ssh_credentials_validation(credentials)
        assert result is False
    
    def test_enhance_ssh_credentials_validation_no_auth(self):
        """Test SSH credentials validation without authentication method"""
        credentials = SSHCredentials(
            hostname="192.168.1.100",
            username="root"
            # No password, key path, or key data
        )
        
        result = enhance_ssh_credentials_validation(credentials)
        assert result is False


class TestRetryPolicyIntegration:
    """Test retry policy integration with SSH manager"""
    
    @pytest.fixture
    def ssh_credentials(self):
        """Create SSH credentials"""
        return SSHCredentials(
            hostname="192.168.1.100",
            username="root", 
            password="password"
        )
    
    def test_retry_execution_success_on_second_attempt(self, ssh_credentials):
        """Test command execution succeeds on retry"""
        config = ReliableSSHConfig(
            enable_network_validation=False,  # Disable to focus on retry
            enable_retry_policy=True,
            max_retry_attempts=2
        )
        reliable_manager = ReliableSSHManager(config=config)
        
        from cyris.tools.ssh_manager import SSHResult
        
        # First attempt fails, second succeeds
        failed_result = SSHResult(
            hostname=ssh_credentials.hostname,
            command="echo test",
            return_code=1,
            stdout="",
            stderr="Command failed",
            execution_time=0.1,
            success=False,
            error_message="Command failed"
        )
        
        success_result = SSHResult(
            hostname=ssh_credentials.hostname,
            command="echo test",
            return_code=0,
            stdout="test",
            stderr="",
            execution_time=0.1,
            success=True
        )
        
        with patch.object(reliable_manager.ssh_manager, 'execute_command') as mock_execute:
            mock_execute.side_effect = [failed_result, success_result]
            
            with patch('time.sleep'):  # Speed up test by mocking sleep
                result = reliable_manager.execute_command_with_reliability(
                    ssh_credentials,
                    "echo test",
                    retry_policy=RetryPolicy(max_attempts=2)
                )
                
                assert result.success is True
                assert result.stdout == "test"
                assert mock_execute.call_count == 2
    
    def test_retry_execution_all_attempts_fail(self, ssh_credentials):
        """Test command execution when all retry attempts fail"""
        config = ReliableSSHConfig(
            enable_network_validation=False,
            enable_retry_policy=True,
            max_retry_attempts=2
        )
        reliable_manager = ReliableSSHManager(config=config)
        
        from cyris.tools.ssh_manager import SSHResult
        
        failed_result = SSHResult(
            hostname=ssh_credentials.hostname,
            command="echo test",
            return_code=1,
            stdout="",
            stderr="Command failed",
            execution_time=0.1,
            success=False,
            error_message="Command failed"
        )
        
        with patch.object(reliable_manager.ssh_manager, 'execute_command') as mock_execute:
            mock_execute.return_value = failed_result
            
            with patch('time.sleep'):
                result = reliable_manager.execute_command_with_reliability(
                    ssh_credentials,
                    "echo test",
                    retry_policy=RetryPolicy(max_attempts=2)
                )
                
                assert result.success is False
                assert mock_execute.call_count == 2