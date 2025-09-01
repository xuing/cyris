"""
Test network service integration
测试网络服务集成
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.services.network_service import (
    NetworkService, NetworkServiceConfig, validate_network_config, check_host_connectivity
)
from cyris.core.network_reliability import NetworkValidationResult, NetworkTestResult


class TestNetworkServiceConfig:
    """Test network service configuration"""
    
    def test_default_config_values(self):
        """Test default configuration values"""
        config = NetworkServiceConfig()
        
        assert config.max_ssh_connections == 10
        assert config.default_ssh_timeout == 30
        assert config.health_check_interval == 60
        assert config.enable_connection_pooling is True
    
    def test_custom_config_values(self):
        """Test custom configuration values"""
        config = NetworkServiceConfig(
            max_ssh_connections=5,
            default_ssh_timeout=15,
            health_check_interval=30,
            enable_connection_pooling=False
        )
        
        assert config.max_ssh_connections == 5
        assert config.default_ssh_timeout == 15
        assert config.health_check_interval == 30
        assert config.enable_connection_pooling is False


class TestNetworkService:
    """Test network service functionality"""
    
    @pytest.fixture
    def network_service(self):
        """Create network service for testing"""
        config = NetworkServiceConfig(enable_connection_pooling=True)
        return NetworkService(config)
    
    @pytest.fixture 
    def network_service_no_pooling(self):
        """Create network service without connection pooling"""
        config = NetworkServiceConfig(enable_connection_pooling=False)
        return NetworkService(config)
    
    def test_network_service_initialization_with_pooling(self, network_service):
        """Test network service initialization with pooling enabled"""
        assert network_service.config.enable_connection_pooling is True
        assert network_service.ssh_manager is not None
        assert network_service.validator is not None
    
    def test_network_service_initialization_without_pooling(self, network_service_no_pooling):
        """Test network service initialization without pooling"""
        assert network_service_no_pooling.config.enable_connection_pooling is False
        assert network_service_no_pooling.ssh_manager is None
        assert network_service_no_pooling.validator is not None
    
    def test_validate_network_configuration_success(self, network_service):
        """Test successful network configuration validation"""
        valid_config = {
            "network_mode": "bridge",
            "bridge_name": "virbr0",
            "enable_ssh": True
        }
        
        result = network_service.validate_network_configuration(valid_config)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_network_configuration_failure(self, network_service):
        """Test network configuration validation with errors"""
        invalid_config = {
            "network_mode": "invalid",
            "bridge_name": "",
            "enable_ssh": "not_boolean"
        }
        
        result = network_service.validate_network_configuration(invalid_config)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    @patch('cyris.services.network_service.validate_ssh_connectivity')
    def test_test_ssh_connectivity_success(self, mock_validate, network_service):
        """Test SSH connectivity testing"""
        mock_validate.return_value = NetworkTestResult(success=True, response_time=0.5)
        
        result = network_service.test_ssh_connectivity("192.168.1.1", 22)
        
        assert result.success is True
        assert result.response_time == 0.5
        mock_validate.assert_called_once_with("192.168.1.1", 22, 5.0)
    
    @patch('cyris.services.network_service.validate_ssh_connectivity')
    def test_test_ssh_connectivity_failure(self, mock_validate, network_service):
        """Test SSH connectivity testing failure"""
        mock_validate.return_value = NetworkTestResult(
            success=False, 
            error_message="Connection refused"
        )
        
        result = network_service.test_ssh_connectivity("192.168.1.1", 22)
        
        assert result.success is False
        assert result.error_message == "Connection refused"
    
    def test_create_ssh_connection_with_pooling(self, network_service):
        """Test SSH connection creation with pooling enabled"""
        with patch.object(network_service.ssh_manager, 'create_connection') as mock_create:
            mock_connection = Mock()
            mock_create.return_value = mock_connection
            
            connection = network_service.create_ssh_connection(
                hostname="192.168.1.1",
                username="root",
                password="password"
            )
            
            assert connection == mock_connection
            mock_create.assert_called_once()
    
    def test_create_ssh_connection_without_pooling(self, network_service_no_pooling):
        """Test SSH connection creation without pooling"""
        connection = network_service_no_pooling.create_ssh_connection(
            hostname="192.168.1.1",
            username="root"
        )
        
        # Should return None when pooling disabled
        assert connection is None
    
    def test_get_ssh_connection_with_pooling(self, network_service):
        """Test getting SSH connection with pooling enabled"""
        with patch.object(network_service.ssh_manager, 'get_connection') as mock_get:
            mock_connection = Mock()
            mock_get.return_value = mock_connection
            
            connection = network_service.get_ssh_connection("192.168.1.1")
            
            assert connection == mock_connection
            mock_get.assert_called_once_with("192.168.1.1")
    
    def test_get_ssh_connection_without_pooling(self, network_service_no_pooling):
        """Test getting SSH connection without pooling"""
        connection = network_service_no_pooling.get_ssh_connection("192.168.1.1")
        
        # Should return None when pooling disabled
        assert connection is None
    
    def test_check_ssh_health_with_pooling(self, network_service):
        """Test SSH health checking with pooling enabled"""
        with patch.object(network_service.ssh_manager, 'check_connection_health') as mock_check:
            mock_check.return_value = True
            
            is_healthy = network_service.check_ssh_health("192.168.1.1")
            
            assert is_healthy is True
            mock_check.assert_called_once_with("192.168.1.1")
    
    def test_check_ssh_health_without_pooling(self, network_service_no_pooling):
        """Test SSH health checking without pooling"""
        is_healthy = network_service_no_pooling.check_ssh_health("192.168.1.1")
        
        # Should return False when pooling disabled
        assert is_healthy is False
    
    def test_cleanup_ssh_connections_with_pooling(self, network_service):
        """Test SSH connection cleanup with pooling enabled"""
        with patch.object(network_service.ssh_manager, 'close_all_connections') as mock_close:
            network_service.cleanup_ssh_connections()
            
            mock_close.assert_called_once()
    
    def test_cleanup_ssh_connections_without_pooling(self, network_service_no_pooling):
        """Test SSH connection cleanup without pooling"""
        # Should not raise error when pooling disabled
        network_service_no_pooling.cleanup_ssh_connections()
    
    def test_get_network_statistics_with_pooling(self, network_service):
        """Test network statistics with pooling enabled"""
        with patch.object(network_service.ssh_manager, 'get_connection_stats') as mock_stats:
            mock_stats.return_value = {"active_connections": 2, "max_connections": 10}
            
            stats = network_service.get_network_statistics()
            
            assert "config" in stats
            assert "ssh_connections" in stats
            assert stats["config"]["pooling_enabled"] is True
            assert stats["ssh_connections"]["active_connections"] == 2
    
    def test_get_network_statistics_without_pooling(self, network_service_no_pooling):
        """Test network statistics without pooling"""
        stats = network_service_no_pooling.get_network_statistics()
        
        assert "config" in stats
        assert "ssh_connections" in stats
        assert stats["config"]["pooling_enabled"] is False
        assert stats["ssh_connections"]["status"] == "disabled"
    
    def test_shutdown(self, network_service):
        """Test network service shutdown"""
        with patch.object(network_service, 'cleanup_ssh_connections') as mock_cleanup:
            network_service.shutdown()
            
            mock_cleanup.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('cyris.services.network_service.NetworkValidator')
    def test_validate_network_config_convenience(self, mock_validator_class):
        """Test validate_network_config convenience function"""
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        mock_result = NetworkValidationResult(is_valid=True)
        mock_validator.validate_network_config.return_value = mock_result
        
        config = {"network_mode": "bridge"}
        result = validate_network_config(config)
        
        assert result == mock_result
        mock_validator.validate_network_config.assert_called_once_with(config)
    
    @patch('cyris.services.network_service.validate_ssh_connectivity')
    def test_check_host_connectivity_success(self, mock_validate):
        """Test check_host_connectivity convenience function success"""
        mock_validate.return_value = NetworkTestResult(success=True)
        
        result = check_host_connectivity("192.168.1.1", 22)
        
        assert result is True
        mock_validate.assert_called_once_with("192.168.1.1", 22, timeout=5.0)
    
    @patch('cyris.services.network_service.validate_ssh_connectivity')
    def test_check_host_connectivity_failure(self, mock_validate):
        """Test check_host_connectivity convenience function failure"""
        mock_validate.return_value = NetworkTestResult(success=False)
        
        result = check_host_connectivity("192.168.1.1", 22)
        
        assert result is False


class TestNetworkServiceIntegration:
    """Integration tests for network service"""
    
    def test_service_lifecycle(self):
        """Test complete service lifecycle"""
        # Initialize service
        config = NetworkServiceConfig(max_ssh_connections=5)
        service = NetworkService(config)
        
        # Test configuration validation
        test_config = {
            "network_mode": "user",
            "enable_ssh": False
        }
        
        validation_result = service.validate_network_configuration(test_config)
        assert validation_result.is_valid is True
        
        # Test statistics
        stats = service.get_network_statistics()
        assert stats["config"]["max_ssh_connections"] == 5
        
        # Shutdown
        service.shutdown()
    
    def test_error_handling_in_validation(self):
        """Test error handling in network validation"""
        service = NetworkService()
        
        # Pass invalid config that causes exception
        with patch.object(service.validator, 'validate_network_config', side_effect=Exception("Test error")):
            result = service.validate_network_configuration({})
            
            assert result.is_valid is False
            assert len(result.errors) == 1
            assert "Validation failed" in result.errors[0]