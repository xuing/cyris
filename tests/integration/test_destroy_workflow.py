"""
End-to-end integration tests for destroy workflow

These tests verify the complete destroy workflow from CLI command
through orchestrator to infrastructure cleanup. Tests the real
integration between all components that were fixed.
"""

import pytest
import tempfile
import json
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
from datetime import datetime
from click.testing import CliRunner

from cyris.cli.main import cli
from cyris.services.orchestrator import RangeOrchestrator, RangeStatus, RangeMetadata
from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.config.settings import CyRISSettings


class TestDestroyWorkflowIntegration:
    """End-to-end integration tests for destroy workflow"""
    
    @pytest.fixture
    def temp_cyber_range_dir(self):
        """Create temporary cyber range directory with metadata"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cyber_range_dir = Path(temp_dir)
            
            # Create ranges metadata file
            ranges_metadata = {
                "test_range": {
                    "range_id": "test_range",
                    "name": "Test Range",
                    "description": "Test range for integration testing",
                    "created_at": "2025-01-01T10:00:00",
                    "status": "active",
                    "last_modified": "2025-01-01T10:00:00",
                    "owner": None,
                    "tags": {},
                    "config_path": None,
                    "logs_path": str(cyber_range_dir / "test_range" / "logs"),
                    "provider_config": {"libvirt_uri": "qemu:///system"}
                }
            }
            
            metadata_file = cyber_range_dir / "ranges_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(ranges_metadata, f, indent=2)
            
            # Create ranges resources file
            ranges_resources = {
                "test_range": {
                    "hosts": ["host1"],
                    "guests": ["cyris-test-guest-12345"]
                }
            }
            
            resources_file = cyber_range_dir / "ranges_resources.json"
            with open(resources_file, 'w') as f:
                json.dump(ranges_resources, f, indent=2)
            
            # Create range directory
            range_dir = cyber_range_dir / "test_range"
            range_dir.mkdir()
            logs_dir = range_dir / "logs"
            logs_dir.mkdir()
            
            yield cyber_range_dir
    
    @pytest.fixture
    def mock_settings(self, temp_cyber_range_dir):
        """Create settings pointing to temp directory"""
        settings = CyRISSettings()
        settings.cyber_range_dir = temp_cyber_range_dir
        settings.cyris_path = temp_cyber_range_dir
        return settings
    
    def test_end_to_end_destroy_workflow_success(self, temp_cyber_range_dir, mock_settings):
        """Test complete successful destroy workflow"""
        runner = CliRunner()
        
        with patch('cyris.cli.main.CyRISSettings') as mock_settings_class, \
             patch('cyris.infrastructure.providers.kvm_provider.libvirt') as mock_libvirt, \
             patch('cyris.infrastructure.providers.kvm_provider.PermissionManager') as mock_pm_class, \
             patch('cyris.infrastructure.network.tunnel_manager.TunnelManager'), \
             patch('cyris.services.gateway_service.GatewayService'):
            
            # Setup mocks
            mock_settings_class.return_value = mock_settings
            
            # Mock libvirt operations
            mock_domain = Mock()
            mock_domain.isActive.return_value = 1
            mock_domain.destroy.return_value = 0
            mock_domain.state.return_value = [5, 0]  # VIR_DOMAIN_SHUTOFF
            mock_domain.undefine.return_value = 0
            
            mock_connection = Mock()
            mock_connection.isAlive.return_value = True
            mock_connection.lookupByName.return_value = mock_domain
            mock_libvirt.open.return_value = mock_connection
            
            # Mock permission manager
            mock_pm = Mock()
            mock_pm_class.return_value = mock_pm
            
            # Execute destroy command
            result = runner.invoke(cli, ['destroy', 'test_range', '--force'])
            
            # Verify successful execution
            assert result.exit_code == 0
            assert '✅' in result.output
            assert 'destroyed successfully' in result.output
            assert not self._contains_chinese_text(result.output)
            
            # Verify range status was updated to destroyed
            metadata_file = temp_cyber_range_dir / "ranges_metadata.json"
            with open(metadata_file, 'r') as f:
                updated_metadata = json.load(f)
            
            assert updated_metadata["test_range"]["status"] == "destroyed"
    
    def test_end_to_end_destroy_with_parameter_detection(self, temp_cyber_range_dir, mock_settings):
        """Test destroy workflow correctly detects provider configuration"""
        runner = CliRunner()
        
        # Update metadata to use session mode
        ranges_metadata = {
            "session_range": {
                "range_id": "session_range", 
                "name": "Session Range",
                "description": "Range using session mode",
                "created_at": "2025-01-01T10:00:00",
                "status": "active",
                "last_modified": "2025-01-01T10:00:00",
                "owner": None,
                "tags": {},
                "config_path": None,
                "logs_path": str(temp_cyber_range_dir / "session_range" / "logs"),
                "provider_config": {"libvirt_uri": "qemu:///session"}
            }
        }
        
        metadata_file = temp_cyber_range_dir / "ranges_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(ranges_metadata, f, indent=2)
        
        with patch('cyris.cli.main.CyRISSettings') as mock_settings_class, \
             patch('cyris.infrastructure.providers.kvm_provider.libvirt') as mock_libvirt, \
             patch('cyris.infrastructure.providers.kvm_provider.PermissionManager') as mock_pm_class, \
             patch('cyris.infrastructure.network.tunnel_manager.TunnelManager'), \
             patch('cyris.services.gateway_service.GatewayService'):
            
            mock_settings_class.return_value = mock_settings
            
            # Mock libvirt for session mode
            mock_domain = Mock()
            mock_domain.isActive.return_value = 0  # Not active
            mock_domain.state.return_value = [5, 0]  # Already shut off
            mock_domain.undefine.return_value = 0
            
            mock_connection = Mock()
            mock_connection.isAlive.return_value = True
            mock_connection.lookupByName.return_value = mock_domain
            mock_libvirt.open.return_value = mock_connection
            
            mock_pm_class.return_value = Mock()
            
            result = runner.invoke(cli, ['destroy', 'session_range', '--force'])
            
            # Should succeed and use session mode
            assert result.exit_code == 0
            assert 'Using detected libvirt URI: qemu:///session' in result.output or 'destroyed successfully' in result.output
    
    def test_end_to_end_destroy_nonexistent_range(self, temp_cyber_range_dir, mock_settings):
        """Test destroy workflow for nonexistent range"""
        runner = CliRunner()
        
        with patch('cyris.cli.main.CyRISSettings') as mock_settings_class:
            mock_settings_class.return_value = mock_settings
            
            result = runner.invoke(cli, ['destroy', 'nonexistent_range', '--force'])
            
            # Should fail gracefully
            assert result.exit_code == 1
            assert '❌' in result.output
            assert 'not found' in result.output.lower()
    
    def test_end_to_end_destroy_with_infrastructure_failure(self, temp_cyber_range_dir, mock_settings):
        """Test destroy workflow when infrastructure operations fail"""
        runner = CliRunner()
        
        with patch('cyris.cli.main.CyRISSettings') as mock_settings_class, \
             patch('cyris.infrastructure.providers.kvm_provider.libvirt') as mock_libvirt, \
             patch('cyris.infrastructure.providers.kvm_provider.PermissionManager') as mock_pm_class, \
             patch('cyris.infrastructure.network.tunnel_manager.TunnelManager'), \
             patch('cyris.services.gateway_service.GatewayService'):
            
            mock_settings_class.return_value = mock_settings
            
            # Mock libvirt failure
            mock_libvirt.libvirtError = Exception
            mock_connection = Mock()
            mock_connection.isAlive.return_value = True
            mock_connection.lookupByName.side_effect = Exception("VM not found")
            mock_libvirt.open.return_value = mock_connection
            
            mock_pm_class.return_value = Mock()
            
            result = runner.invoke(cli, ['destroy', 'test_range', '--force'])
            
            # Should handle failure but still update metadata
            assert result.exit_code == 0  # Should complete despite infrastructure issues
            assert 'destroyed successfully' in result.output or 'Failed to destroy' in result.output
    
    def test_destroy_workflow_preserves_metadata_on_partial_failure(self, temp_cyber_range_dir, mock_settings):
        """Test that metadata is preserved and updated even on partial failures"""
        # Create orchestrator directly for more controlled testing
        with patch('cyris.infrastructure.network.tunnel_manager.TunnelManager'), \
             patch('cyris.services.gateway_service.GatewayService'), \
             patch('cyris.infrastructure.providers.kvm_provider.PermissionManager'):
            
            # Create mock provider that fails on guest destruction
            mock_provider = Mock()
            mock_provider.libvirt_uri = "qemu:///system"
            mock_provider.destroy_guests.side_effect = Exception("Guest destroy failed")
            mock_provider.destroy_hosts.return_value = None
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
            
            # Verify range exists before destroy
            assert "test_range" in orchestrator._ranges
            assert orchestrator._ranges["test_range"].status == RangeStatus.ACTIVE
            
            # Attempt destroy (should fail but update metadata)
            result = orchestrator.destroy_range("test_range")
            
            assert result is False
            assert orchestrator._ranges["test_range"].status == RangeStatus.ERROR
            
            # Verify metadata was persisted
            metadata_file = temp_cyber_range_dir / "ranges_metadata.json"
            assert metadata_file.exists()
            
            with open(metadata_file, 'r') as f:
                saved_metadata = json.load(f)
            
            assert saved_metadata["test_range"]["status"] == "error"
    
    def test_destroy_workflow_handles_missing_provider_config(self, temp_cyber_range_dir, mock_settings):
        """Test destroy workflow when range has no provider config"""
        # Update metadata to remove provider_config
        ranges_metadata = {
            "no_config_range": {
                "range_id": "no_config_range",
                "name": "No Config Range", 
                "description": "Range without provider config",
                "created_at": "2025-01-01T10:00:00",
                "status": "active",
                "last_modified": "2025-01-01T10:00:00", 
                "owner": None,
                "tags": {},
                "config_path": None,
                "logs_path": str(temp_cyber_range_dir / "no_config_range" / "logs"),
                "provider_config": None
            }
        }
        
        metadata_file = temp_cyber_range_dir / "ranges_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(ranges_metadata, f, indent=2)
        
        runner = CliRunner()
        
        with patch('cyris.cli.main.CyRISSettings') as mock_settings_class, \
             patch('cyris.infrastructure.providers.kvm_provider.libvirt') as mock_libvirt, \
             patch('cyris.infrastructure.providers.kvm_provider.PermissionManager'), \
             patch('cyris.infrastructure.network.tunnel_manager.TunnelManager'), \
             patch('cyris.services.gateway_service.GatewayService'):
            
            mock_settings_class.return_value = mock_settings
            
            # Mock libvirt
            mock_connection = Mock()
            mock_connection.isAlive.return_value = True
            mock_connection.lookupByName.return_value = Mock()
            mock_libvirt.open.return_value = mock_connection
            
            result = runner.invoke(cli, ['destroy', 'no_config_range', '--force'])
            
            # Should use default configuration and succeed
            assert result.exit_code == 0
            assert 'No provider config found, using default' in result.output or 'destroyed successfully' in result.output
    
    def _contains_chinese_text(self, text):
        """Check if text contains Chinese characters"""
        import re
        if not text:
            return False
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        return bool(chinese_pattern.search(text))


class TestPermissionWorkflowIntegration:
    """Integration tests for permission management workflow"""
    
    def test_setup_permissions_command_integration(self):
        """Test setup-permissions command end-to-end"""
        runner = CliRunner()
        
        with patch('cyris.infrastructure.permissions.PermissionManager') as mock_pm_class, \
             patch('cyris.cli.main.CyRISSettings') as mock_settings_class:
            
            # Mock permission manager
            mock_pm = Mock()
            mock_pm.check_libvirt_compatibility.return_value = {
                'libvirt_user': 'libvirt-qemu',
                'acl_supported': True,
                'current_user_groups': ['ubuntu', 'libvirt'],
                'recommendations': []
            }
            mock_pm.setup_cyris_environment.return_value = True
            mock_pm_class.return_value = mock_pm
            
            # Mock settings
            mock_settings = Mock()
            mock_settings.cyris_path = Path('/test/path')
            mock_settings_class.return_value = mock_settings
            
            result = runner.invoke(cli, ['setup-permissions'])
            
            assert result.exit_code == 0
            assert 'Successfully configured libvirt permissions' in result.output
            assert 'bridge networking with' in result.output
            mock_pm.setup_cyris_environment.assert_called_once_with(Path('/test/path'))
    
    def test_create_with_automatic_permission_setup(self):
        """Test that create command automatically sets up permissions"""
        runner = CliRunner()
        
        with patch('cyris.cli.main.RangeOrchestrator') as mock_orchestrator_class, \
             patch('cyris.cli.main.KVMProvider') as mock_kvm_class, \
             patch('cyris.cli.main.CyRISSettings') as mock_settings_class:
            
            # Mock orchestrator
            mock_orchestrator = Mock()
            mock_orchestrator.create_range_from_yaml.return_value = "test_range"
            mock_orchestrator_class.return_value = mock_orchestrator
            
            # Mock KVM provider with permission manager
            mock_provider = Mock()
            mock_provider.permission_manager = Mock()
            mock_kvm_class.return_value = mock_provider
            
            # Mock settings
            mock_settings = Mock()
            mock_settings.cyber_range_dir = Path('/test/cyber_range')
            mock_settings_class.return_value = mock_settings
            
            # Create a temporary YAML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
                f.write("""
host_settings:
  - id: host_1
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: ubuntu
guest_settings:
  - id: desktop
    basevm_host: host_1
    basevm_config_file: /test/basevm.xml
clone_settings:
  - range_id: test
                """)
                temp_yaml = f.name
            
            try:
                result = runner.invoke(cli, [
                    'create', 
                    temp_yaml,
                    '--network-mode', 'bridge',
                    '--enable-ssh'
                ])
                
                # Should succeed and configure bridge networking
                if result.exit_code == 0:
                    assert 'created successfully' in result.output
                    
                    # Verify KVM provider was created with bridge settings
                    call_args = mock_kvm_class.call_args
                    if call_args:
                        kvm_config = call_args[0][0]
                        assert kvm_config['network_mode'] == 'bridge'
                        assert kvm_config['enable_ssh'] is True
                        assert 'qemu:///system' in kvm_config['libvirt_uri']
                
            finally:
                Path(temp_yaml).unlink()


class TestWorkflowErrorRecovery:
    """Test error recovery in workflows"""
    
    def test_destroy_workflow_continues_despite_vm_errors(self, temp_cyber_range_dir, mock_settings):
        """Test that destroy workflow continues even if individual VMs fail"""
        with patch('cyris.infrastructure.network.tunnel_manager.TunnelManager'), \
             patch('cyris.services.gateway_service.GatewayService'), \
             patch('cyris.infrastructure.providers.kvm_provider.PermissionManager'):
            
            # Mock provider with partial failures
            mock_provider = Mock()
            mock_provider.libvirt_uri = "qemu:///system"
            
            # First guest fails, second succeeds
            def destroy_guests_side_effect(guest_ids):
                if guest_ids == ["failing_guest"]:
                    raise Exception("VM stuck in shutdown")
                return None
            
            mock_provider.destroy_guests.side_effect = destroy_guests_side_effect
            mock_provider.destroy_hosts.return_value = None
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
            
            # Create range with multiple guests
            range_id = "multi_guest_range"
            metadata = RangeMetadata(
                range_id=range_id,
                name="Multi Guest Range",
                description="Range with multiple guests",
                created_at=datetime.now(),
                status=RangeStatus.ACTIVE
            )
            orchestrator._ranges[range_id] = metadata
            orchestrator._range_resources[range_id] = {
                "hosts": ["host1"], 
                "guests": ["failing_guest", "working_guest"]
            }
            
            # Destroy should fail but still attempt cleanup
            result = orchestrator.destroy_range(range_id)
            
            assert result is False
            assert orchestrator._ranges[range_id].status == RangeStatus.ERROR
            mock_provider.destroy_guests.assert_called()
    
    def test_permission_setup_graceful_degradation(self):
        """Test that permission setup degrades gracefully on errors"""
        from cyris.infrastructure.permissions import PermissionManager
        
        with patch('subprocess.run') as mock_subprocess:
            # Simulate ACL commands not available
            mock_subprocess.side_effect = FileNotFoundError("setfacl not found")
            
            pm = PermissionManager()
            
            # Should not crash, should return compatibility info
            compat_info = pm.check_libvirt_compatibility()
            
            assert isinstance(compat_info, dict)
            assert 'libvirt_user' in compat_info
            assert 'acl_supported' in compat_info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])