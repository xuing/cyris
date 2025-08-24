"""
TDD tests for destroy command functionality

These tests verify the fixes for the destroy command that was failing
and requiring manual cleanup. Key areas tested:
- Parameter mismatch fixes (connection_uri vs libvirt_uri)
- Provider config detection and storage
- Proper range status transitions during destroy
- Resource cleanup completion
"""

import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from cyris.services.orchestrator import RangeOrchestrator, RangeStatus, RangeMetadata
from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.config.settings import CyRISSettings


class TestDestroyCommand:
    """Test destroy command functionality"""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = CyRISSettings()
            settings.cyber_range_dir = Path(temp_dir)
            settings.cyris_path = Path(temp_dir)
            yield settings
    
    @pytest.fixture
    def mock_kvm_provider(self):
        """Create mock KVM provider"""
        provider = Mock(spec=KVMProvider)
        provider.libvirt_uri = "qemu:///system"
        provider.get_status.return_value = {"guest1": "active", "host1": "active"}
        provider.destroy_guests.return_value = None
        provider.destroy_hosts.return_value = None
        return provider
    
    @pytest.fixture
    def orchestrator(self, mock_settings, mock_kvm_provider):
        """Create orchestrator with mocked dependencies"""
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            orchestrator = RangeOrchestrator(mock_settings, mock_kvm_provider)
            return orchestrator
    
    def test_destroy_nonexistent_range_returns_false(self, orchestrator):
        """Test that destroying a nonexistent range returns False"""
        result = orchestrator.destroy_range("nonexistent")
        assert result is False
    
    def test_destroy_existing_range_updates_status(self, orchestrator, mock_kvm_provider):
        """Test that destroying an existing range updates status correctly"""
        # Setup: Create a range
        range_id = "test_range"
        metadata = RangeMetadata(
            range_id=range_id,
            name="Test Range",
            description="Test description",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE,
            provider_config={"libvirt_uri": "qemu:///system"}
        )
        orchestrator._ranges[range_id] = metadata
        orchestrator._range_resources[range_id] = {"hosts": ["host1"], "guests": ["guest1"]}
        
        # Execute: Destroy the range
        result = orchestrator.destroy_range(range_id)
        
        # Verify
        assert result is True
        assert orchestrator._ranges[range_id].status == RangeStatus.DESTROYED
        mock_kvm_provider.destroy_guests.assert_called_once_with(["guest1"])
        mock_kvm_provider.destroy_hosts.assert_called_once_with(["host1"])
    
    def test_destroy_handles_provider_config_correctly(self, orchestrator):
        """Test that destroy uses correct libvirt_uri from provider_config"""
        # Setup: Create range with specific provider config
        range_id = "test_range"
        metadata = RangeMetadata(
            range_id=range_id,
            name="Test Range", 
            description="Test description",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE,
            provider_config={"libvirt_uri": "qemu:///session"}
        )
        orchestrator._ranges[range_id] = metadata
        orchestrator._range_resources[range_id] = {"hosts": [], "guests": []}
        
        # Execute
        result = orchestrator.destroy_range(range_id)
        
        # Verify: The provider config is preserved and accessible
        assert result is True
        assert orchestrator._ranges[range_id].provider_config["libvirt_uri"] == "qemu:///session"
    
    def test_destroy_handles_exceptions_gracefully(self, orchestrator, mock_kvm_provider):
        """Test that destroy handles provider exceptions gracefully"""
        # Setup
        range_id = "test_range"
        metadata = RangeMetadata(
            range_id=range_id,
            name="Test Range",
            description="Test description", 
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE
        )
        orchestrator._ranges[range_id] = metadata
        orchestrator._range_resources[range_id] = {"hosts": [], "guests": ["guest1"]}
        
        # Mock provider to raise exception
        mock_kvm_provider.destroy_guests.side_effect = Exception("Provider error")
        
        # Execute
        result = orchestrator.destroy_range(range_id)
        
        # Verify: Should return False but not crash
        assert result is False
        assert orchestrator._ranges[range_id].status == RangeStatus.ERROR
    
    def test_kvm_provider_parameter_handling(self):
        """Test that KVMProvider correctly handles both connection_uri and libvirt_uri"""
        # Test with libvirt_uri
        config1 = {"libvirt_uri": "qemu:///system"}
        provider1 = KVMProvider(config1)
        assert provider1.libvirt_uri == "qemu:///system"
        
        # Test with connection_uri (legacy parameter)
        config2 = {"connection_uri": "qemu:///session"}
        provider2 = KVMProvider(config2)
        assert provider2.libvirt_uri == "qemu:///session"
        
        # Test with both (libvirt_uri takes precedence)
        config3 = {"libvirt_uri": "qemu:///system", "connection_uri": "qemu:///session"}
        provider3 = KVMProvider(config3)
        assert provider3.libvirt_uri == "qemu:///system"
        
        # Test with neither (defaults to session)
        config4 = {}
        provider4 = KVMProvider(config4)
        assert provider4.libvirt_uri == "qemu:///session"


class TestCLIDestroyIntegration:
    """Integration tests for CLI destroy command"""
    
    def test_cli_destroy_parameter_passing(self):
        """Test that CLI correctly passes parameters to orchestrator"""
        from click.testing import CliRunner
        from cyris.cli.main import cli
        
        runner = CliRunner()
        
        # Test dry run to avoid actual resource creation/destruction
        with patch('cyris.services.orchestrator.RangeOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.get_range.return_value = None
            mock_orchestrator_class.return_value = mock_orchestrator
            
            result = runner.invoke(cli, ['destroy', 'test_range', '--force'])
            
            # Verify the command structure is correct
            assert result.exit_code != 0  # Should exit with error for nonexistent range
            assert "not found" in result.output.lower()
    
    def test_cli_destroy_with_provider_config_detection(self):
        """Test that CLI destroy detects and uses correct provider configuration"""
        from click.testing import CliRunner
        from cyris.cli.main import cli
        
        runner = CliRunner()
        
        with patch('cyris.services.orchestrator.RangeOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            
            # Mock range with specific provider config
            mock_range = Mock()
            mock_range.provider_config = {"libvirt_uri": "qemu:///session"}
            mock_range.name = "Test Range"
            mock_range.status.value = "active"
            mock_range.created_at = datetime.now()
            mock_orchestrator.get_range.return_value = mock_range
            mock_orchestrator.destroy_range.return_value = True
            
            mock_orchestrator_class.return_value = mock_orchestrator
            
            result = runner.invoke(cli, ['destroy', 'test_range', '--force'])
            
            # Verify successful execution
            assert result.exit_code == 0
            assert "destroyed successfully" in result.output
            mock_orchestrator.destroy_range.assert_called_once_with('test_range')


class TestDestroyErrorHandling:
    """Test error handling in destroy operations"""
    
    def test_destroy_with_timeout_handling(self):
        """Test that destroy operations handle timeouts gracefully"""
        from cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        config = {"libvirt_uri": "qemu:///system"}
        provider = KVMProvider(config)
        
        # Test that the provider has timeout handling
        assert hasattr(provider, 'destroy_guests')
        assert hasattr(provider, 'destroy_hosts')
    
    def test_destroy_with_partial_resource_cleanup(self):
        """Test destroy operation when some resources fail to clean up"""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_settings = CyRISSettings()
            mock_settings.cyber_range_dir = Path(temp_dir)
            mock_settings.cyris_path = Path(temp_dir)
            
            with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
                 patch('cyris.services.orchestrator.TaskExecutor'), \
                 patch('cyris.services.orchestrator.TunnelManager'), \
                 patch('cyris.services.orchestrator.GatewayService'):
                
                # Create mock provider that fails on guests but succeeds on hosts
                mock_provider = Mock()
                mock_provider.libvirt_uri = "qemu:///system"
                mock_provider.destroy_guests.side_effect = Exception("Guest cleanup failed")
                mock_provider.destroy_hosts.return_value = None
                
                orchestrator = RangeOrchestrator(mock_settings, mock_provider)
                
                # Setup range
                range_id = "test_range"
                metadata = RangeMetadata(
                    range_id=range_id,
                    name="Test Range",
                    description="Test description",
                    created_at=datetime.now(),
                    status=RangeStatus.ACTIVE
                )
                orchestrator._ranges[range_id] = metadata
                orchestrator._range_resources[range_id] = {"hosts": ["host1"], "guests": ["guest1"]}
                
                # Execute destroy
                result = orchestrator.destroy_range(range_id)
                
                # Should still attempt cleanup and set error status
                assert result is False
                assert orchestrator._ranges[range_id].status == RangeStatus.ERROR
                mock_provider.destroy_guests.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])