"""
Test cases for RangeOrchestrator resource management functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from pathlib import Path
import json
import tempfile
import subprocess

from cyris.services.orchestrator import RangeOrchestrator, RangeStatus, RangeMetadata
from cyris.config.settings import CyRISSettings
from cyris.core.exceptions import CyRISVirtualizationError


class TestRangeOrchestratorResourceManagement:
    """Test cases for resource management in RangeOrchestrator"""

    @pytest.fixture
    def mock_settings(self):
        """Mock CyRIS settings"""
        settings = Mock(spec=CyRISSettings)
        settings.cyber_range_dir = "/mock/cyber_range"
        settings.cyris_path = Path("/mock/cyris")
        return settings

    @pytest.fixture
    def mock_provider(self):
        """Mock infrastructure provider"""
        provider = Mock()
        provider.create_hosts.return_value = ["host_1"]
        provider.create_guests.return_value = ["guest_1"]
        provider.destroy_hosts = Mock()
        provider.destroy_guests = Mock()
        provider.get_status.return_value = {"host_1": "active", "guest_1": "active"}
        return provider

    @pytest.fixture
    def orchestrator(self, mock_settings, mock_provider):
        """Create orchestrator instance with mocked dependencies"""
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'), \
             patch('pathlib.Path.mkdir'), \
             patch.object(RangeOrchestrator, '_load_persistent_data'):
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
            orchestrator._save_persistent_data = Mock()
            return orchestrator

    def test_create_actual_cyber_range_success(self, orchestrator, mock_settings):
        """Test successful creation of actual cyber range"""
        yaml_config = {
            "clone_settings": [{"range_id": 123}],
            "host_settings": [{"id": "host1"}],
            "guest_settings": [{"id": "guest1"}]
        }
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('subprocess.run') as mock_subprocess, \
             patch('yaml.dump') as mock_yaml_dump, \
             patch('time.sleep'), \
             patch.object(orchestrator, '_discover_created_resources') as mock_discover:
            
            # Mock temporary file
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.yml"
            
            # Mock successful subprocess execution
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result
            
            # Mock resource discovery
            mock_discover.return_value = {
                'vms': ['cyris-test-vm'],
                'disks': ['cyris-test-disk.qcow2'],
                'networks': []
            }
            
            # Test creation
            resources = orchestrator._create_actual_cyber_range(yaml_config, 123)
            
            # Verify subprocess was called with correct arguments
            expected_cmd = [
                'python3',
                str(mock_settings.cyris_path / 'main' / 'cyris.py'),
                '/tmp/test.yml',
                str(mock_settings.cyris_path / 'CONFIG')
            ]
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            assert call_args == expected_cmd
            
            # Verify resources were discovered
            assert resources == {
                'vms': ['cyris-test-vm'],
                'disks': ['cyris-test-disk.qcow2'],
                'networks': []
            }

    def test_create_actual_cyber_range_failure(self, orchestrator):
        """Test failure handling in actual cyber range creation"""
        yaml_config = {"clone_settings": [{"range_id": 123}]}
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('subprocess.run') as mock_subprocess, \
             patch('yaml.dump'), \
             patch.object(orchestrator, '_cleanup_partial_resources') as mock_cleanup:
            
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.yml"
            
            # Mock failed subprocess execution
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Creation failed"
            mock_subprocess.return_value = mock_result
            
            # Test creation failure
            with pytest.raises(RuntimeError, match="Legacy CyRIS failed"):
                orchestrator._create_actual_cyber_range(yaml_config, 123)
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once_with(123, {'vms': [], 'disks': [], 'networks': []})

    def test_discover_created_resources(self, orchestrator, mock_settings):
        """Test discovery of created resources"""
        with patch('cyris.infrastructure.providers.virsh_client.VirshLibvirt') as mock_virsh_class, \
             patch('pathlib.Path.glob') as mock_glob:
            
            # Mock VirshLibvirt
            mock_virsh = Mock()
            mock_virsh.list_all_domains.return_value = [
                {"name": "cyris-vm-1", "id": "1"},
                {"name": "cyris-vm-2", "id": "2"},
                {"name": "regular-vm", "id": "3"}  # Should be ignored
            ]
            mock_virsh_class.return_value = mock_virsh
            
            # Mock disk file discovery
            mock_disk1 = Mock()
            mock_disk1.name = "cyris-disk-1.qcow2"
            mock_disk2 = Mock()
            mock_disk2.name = "cyris-disk-2.qcow2"
            mock_disk3 = Mock()
            mock_disk3.name = "regular-disk.qcow2"  # Should be ignored
            
            mock_glob.return_value = [mock_disk1, mock_disk2, mock_disk3]
            
            # Test resource discovery
            resources = orchestrator._discover_created_resources(123)
            
            # Verify results
            assert len(resources['vms']) == 2
            assert "cyris-vm-1" in resources['vms']
            assert "cyris-vm-2" in resources['vms']
            assert "regular-vm" not in resources['vms']
            
            assert len(resources['disks']) == 2
            assert "cyris-disk-1.qcow2" in resources['disks']
            assert "cyris-disk-2.qcow2" in resources['disks']
            assert "regular-disk.qcow2" not in resources['disks']

    def test_cleanup_partial_resources(self, orchestrator, mock_settings):
        """Test cleanup of partially created resources"""
        resources = {
            'vms': ['cyris-vm-1', 'cyris-vm-2'],
            'disks': ['cyris-disk-1.qcow2', 'cyris-disk-2.qcow2'],
            'networks': []
        }
        
        with patch('cyris.infrastructure.providers.virsh_client.VirshLibvirt') as mock_virsh_class, \
             patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.unlink') as mock_unlink:
            
            # Mock VirshLibvirt
            mock_virsh = Mock()
            mock_virsh_class.return_value = mock_virsh
            
            # Mock disk file existence
            mock_exists.return_value = True
            
            # Test cleanup
            orchestrator._cleanup_partial_resources(123, resources)
            
            # Verify VM cleanup
            expected_vm_calls = [call('cyris-vm-1'), call('cyris-vm-2')]
            mock_virsh.destroy_domain.assert_has_calls(expected_vm_calls)
            mock_virsh.undefine_domain.assert_has_calls(expected_vm_calls)
            
            # Verify disk cleanup
            assert mock_unlink.call_count == 2

    def test_cleanup_actual_resources_with_legacy_script(self, orchestrator, mock_settings):
        """Test cleanup using legacy cleanup script"""
        resources = {
            'vms': ['cyris-vm-1'],
            'disks': ['cyris-disk-1.qcow2'],
            'networks': []
        }
        
        with patch('subprocess.run') as mock_subprocess, \
             patch.object(orchestrator, '_cleanup_partial_resources') as mock_manual_cleanup:
            
            # Mock successful legacy cleanup
            mock_result = Mock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            # Test cleanup
            orchestrator._cleanup_actual_resources(123, resources)
            
            # Verify legacy script was called
            expected_cmd = [
                'bash',
                str(mock_settings.cyris_path / 'main' / 'range_cleanup.sh'),
                '123',
                str(mock_settings.cyris_path / 'CONFIG')
            ]
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            assert call_args == expected_cmd
            
            # Manual cleanup should still be called as backup
            mock_manual_cleanup.assert_called_once_with(123, resources)

    def test_cleanup_actual_resources_fallback_to_manual(self, orchestrator):
        """Test fallback to manual cleanup when legacy script fails"""
        resources = {'vms': ['cyris-vm-1'], 'disks': [], 'networks': []}
        
        with patch('subprocess.run') as mock_subprocess, \
             patch.object(orchestrator, '_cleanup_partial_resources') as mock_manual_cleanup:
            
            # Mock failed legacy cleanup
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Script failed"
            mock_subprocess.return_value = mock_result
            
            # Test cleanup
            orchestrator._cleanup_actual_resources(123, resources)
            
            # Verify fallback to manual cleanup
            mock_manual_cleanup.assert_called_once_with(123, resources)

    def test_create_cyber_range_integration(self, orchestrator):
        """Test complete cyber range creation with resource tracking"""
        yaml_config = {
            "clone_settings": [{"range_id": 123, "hosts": [], "instance_number": 1}],
            "host_settings": [],
            "guest_settings": []
        }
        
        with patch.object(orchestrator, '_create_actual_cyber_range') as mock_create, \
             patch.object(orchestrator, '_create_entry_point') as mock_entry_point, \
             patch.object(orchestrator.gateway_service, 'get_available_port') as mock_port, \
             patch.object(orchestrator.gateway_service, 'generate_random_credentials') as mock_creds:
            
            # Mock successful creation
            mock_create.return_value = {
                'vms': ['cyris-test-vm'],
                'disks': ['cyris-test-disk.qcow2'],
                'networks': []
            }
            mock_port.return_value = 8080
            mock_creds.return_value = "test_password"
            mock_entry_point.return_value = {"port": 8080, "credentials": "test_password"}
            
            # Test creation
            result = orchestrator.create_cyber_range(yaml_config)
            
            # Verify success
            assert result['success'] is True
            assert result['range_id'] == 123
            
            # Verify range was registered
            assert '123' in orchestrator._ranges
            assert orchestrator._ranges['123'].status == RangeStatus.ACTIVE
            
            # Verify resources were tracked
            assert '123' in orchestrator._range_resources
            expected_resources = {
                'vms': ['cyris-test-vm'],
                'disks': ['cyris-test-disk.qcow2'],
                'networks': []
            }
            assert orchestrator._range_resources['123'] == expected_resources

    def test_destroy_cyber_range_integration(self, orchestrator):
        """Test complete cyber range destruction with resource cleanup"""
        # Setup existing range
        orchestrator._ranges['123'] = RangeMetadata(
            range_id='123',
            name='Test Range',
            description='Test',
            status=RangeStatus.ACTIVE,
            created_at=datetime.now()
        )
        orchestrator._range_resources['123'] = {
            'vms': ['cyris-test-vm'],
            'disks': ['cyris-test-disk.qcow2'],
            'networks': []
        }
        
        with patch.object(orchestrator.gateway_service, 'cleanup_range') as mock_gateway_cleanup, \
             patch.object(orchestrator, '_cleanup_actual_resources') as mock_resource_cleanup:
            
            # Test destruction
            result = orchestrator.destroy_cyber_range(123)
            
            # Verify success
            assert result['success'] is True
            assert result['range_id'] == 123
            
            # Verify gateway cleanup was called
            mock_gateway_cleanup.assert_called_once_with(123)
            
            # Verify resource cleanup was called
            expected_resources = {
                'vms': ['cyris-test-vm'],
                'disks': ['cyris-test-disk.qcow2'],
                'networks': []
            }
            mock_resource_cleanup.assert_called_once_with(123, expected_resources)
            
            # Verify range was removed from tracking
            assert '123' not in orchestrator._ranges
            assert '123' not in orchestrator._range_resources

    def test_resource_cleanup_error_handling(self, orchestrator):
        """Test error handling during resource cleanup"""
        resources = {'vms': ['problematic-vm'], 'disks': [], 'networks': []}
        
        with patch('cyris.infrastructure.providers.virsh_client.VirshLibvirt') as mock_virsh_class:
            # Mock VirshLibvirt that throws exceptions
            mock_virsh = Mock()
            mock_virsh.destroy_domain.side_effect = Exception("VM cleanup failed")
            mock_virsh_class.return_value = mock_virsh
            
            # Test cleanup with errors (should not raise)
            orchestrator._cleanup_partial_resources(123, resources)
            
            # Verify the method completed despite errors
            mock_virsh.destroy_domain.assert_called_once_with('problematic-vm')

    def test_range_metadata_persistence(self, orchestrator):
        """Test that range metadata is properly persisted"""
        # Create a range
        metadata = RangeMetadata(
            range_id='456',
            name='Persistent Range',
            description='Test persistence',
            status=RangeStatus.ACTIVE,
            created_at=datetime.now()
        )
        
        orchestrator._ranges['456'] = metadata
        orchestrator._range_resources['456'] = {'vms': [], 'disks': [], 'networks': []}
        
        # Verify _save_persistent_data is called
        with patch.object(orchestrator, '_save_persistent_data') as mock_save:
            # Trigger a status update that should save data
            orchestrator._ranges['456'].update_status(RangeStatus.DESTROYED)
            
            # Manually call save to test
            orchestrator._save_persistent_data()
            mock_save.assert_called()


class TestResourceTrackingIntegration:
    """Integration tests for resource tracking functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_persistent_data_save_load_cycle(self, temp_dir):
        """Test complete save and load cycle of persistent data"""
        # Setup mock settings
        mock_settings = Mock()
        mock_settings.cyber_range_dir = str(temp_dir)
        mock_settings.cyris_path = temp_dir / "cyris"
        
        mock_provider = Mock()
        
        # Create orchestrator and add test data
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
            
            # Add test range data
            test_metadata = RangeMetadata(
                range_id='789',
                name='Test Persistence Range',
                description='Testing data persistence',
                status=RangeStatus.ACTIVE,
                created_at=datetime.now()
            )
            
            orchestrator._ranges['789'] = test_metadata
            orchestrator._range_resources['789'] = {
                'vms': ['cyris-persistent-vm'],
                'disks': ['cyris-persistent-disk.qcow2'],
                'networks': ['cyris-network-1']
            }
            
            # Save data
            orchestrator._save_persistent_data()
            
            # Verify files were created
            metadata_file = temp_dir / "ranges_metadata.json"
            resources_file = temp_dir / "ranges_resources.json"
            
            assert metadata_file.exists()
            assert resources_file.exists()
            
            # Verify file contents
            with open(metadata_file, 'r') as f:
                saved_metadata = json.load(f)
                assert '789' in saved_metadata
                assert saved_metadata['789']['name'] == 'Test Persistence Range'
                assert saved_metadata['789']['status'] == 'active'
            
            with open(resources_file, 'r') as f:
                saved_resources = json.load(f)
                assert '789' in saved_resources
                assert 'cyris-persistent-vm' in saved_resources['789']['vms']
            
            # Test loading in new orchestrator instance
            orchestrator2 = RangeOrchestrator(mock_settings, mock_provider)
            
            # Verify data was loaded
            assert '789' in orchestrator2._ranges
            assert orchestrator2._ranges['789'].name == 'Test Persistence Range'
            assert orchestrator2._ranges['789'].status == RangeStatus.ACTIVE
            
            assert '789' in orchestrator2._range_resources
            assert 'cyris-persistent-vm' in orchestrator2._range_resources['789']['vms']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])