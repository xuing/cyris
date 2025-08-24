"""
End-to-end tests for resource management functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
from datetime import datetime
from pathlib import Path

from cyris.services.orchestrator import RangeOrchestrator, RangeStatus, RangeMetadata
from cyris.services.range_discovery import RangeDiscoveryService, OrphanedResource
from cyris.config.settings import CyRISSettings


class TestResourceManagementE2E:
    """End-to-end tests for resource management workflow"""
    
    @pytest.fixture
    def temp_cyber_range_dir(self):
        """Create temporary cyber range directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_settings(self, temp_cyber_range_dir):
        """Mock settings with temporary directory"""
        settings = Mock(spec=CyRISSettings)
        settings.cyber_range_dir = str(temp_cyber_range_dir)
        settings.cyris_path = temp_cyber_range_dir / "cyris"
        return settings
    
    @pytest.fixture
    def mock_provider(self):
        """Mock infrastructure provider"""
        provider = Mock()
        provider.create_hosts.return_value = ["host_123"]
        provider.create_guests.return_value = ["cyris-desktop-abc123"]
        provider.destroy_hosts = Mock()
        provider.destroy_guests = Mock()
        provider.get_status.return_value = {"host_123": "active", "cyris-desktop-abc123": "active"}
        return provider
    
    def test_complete_range_lifecycle_with_resource_tracking(self, mock_settings, mock_provider, temp_cyber_range_dir):
        """Test complete lifecycle: create -> track -> discover -> destroy -> cleanup"""
        
        # Step 1: Create orchestrator
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
        
        # Step 2: Create cyber range with resource tracking
        yaml_config = {
            "clone_settings": [{"range_id": 123, "hosts": [], "instance_number": 1}],
            "host_settings": [{"id": "host1"}],
            "guest_settings": [{"id": "guest1"}]
        }
        
        with patch.object(orchestrator, '_create_actual_cyber_range') as mock_create:
            mock_create.return_value = {
                'vms': ['cyris-desktop-abc123'],
                'disks': ['cyris-desktop-abc123.qcow2'],
                'networks': ['cyris-network-123']
            }
            
            result = orchestrator.create_cyber_range(yaml_config)
            
            # Verify creation success
            assert result['success'] is True
            assert result['range_id'] == 123
            
            # Verify range is tracked
            assert '123' in orchestrator._ranges
            assert orchestrator._ranges['123'].status == RangeStatus.ACTIVE
            
            # Verify resources are tracked
            assert '123' in orchestrator._range_resources
            expected_resources = {
                'vms': ['cyris-desktop-abc123'],
                'disks': ['cyris-desktop-abc123.qcow2'],
                'networks': ['cyris-network-123']
            }
            assert orchestrator._range_resources['123'] == expected_resources
        
        # Step 3: Create discovery service and verify tracking
        discovery_service = RangeDiscoveryService(mock_settings, orchestrator)
        
        with patch.object(discovery_service, '_discover_virtual_machines') as mock_vms, \
             patch.object(discovery_service, '_discover_disk_files') as mock_disks, \
             patch.object(discovery_service, '_discover_range_directories') as mock_dirs:
            
            # Mock discovered resources matching what we created
            mock_vms.return_value = [
                OrphanedResource("vm", "cyris-desktop-abc123", state="running")
            ]
            mock_disks.return_value = [
                OrphanedResource("disk", "cyris-desktop-abc123.qcow2", path="/mock/path")
            ]
            mock_dirs.return_value = [
                OrphanedResource("directory", "123", range_id="123")
            ]
            
            # Discover all ranges
            discovery_result = discovery_service.discover_all_ranges()
            
            # Verify no orphaned resources (all are managed)
            assert discovery_result['orphaned_vms'] == 0
            assert discovery_result['orphaned_disks'] == 0
            assert discovery_result['orphaned_directories'] == 0
            assert discovery_result['total_orphaned_resources'] == 0
        
        # Step 4: Destroy range
        with patch.object(orchestrator, '_cleanup_actual_resources') as mock_cleanup:
            result = orchestrator.destroy_cyber_range(123)
            
            # Verify destruction success
            assert result['success'] is True
            assert result['range_id'] == 123
            
            # Verify range status updated
            # Note: Range should be removed from _ranges after destruction
            assert '123' not in orchestrator._ranges
            
            # Verify cleanup was called with correct resources
            mock_cleanup.assert_called_once_with(123, expected_resources)
        
        # Step 5: Verify no resources remain tracked
        assert '123' not in orchestrator._range_resources
    
    def test_orphaned_resource_recovery_workflow(self, mock_settings, temp_cyber_range_dir):
        """Test workflow for recovering orphaned resources"""
        
        # Step 1: Create orchestrator with some managed ranges
        mock_provider = Mock()
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
            
            # Add one managed range
            orchestrator._ranges['456'] = RangeMetadata(
                range_id='456',
                name='Managed Range',
                description='Properly managed',
                status=RangeStatus.ACTIVE,
                created_at=datetime.now()
            )
            orchestrator._range_resources['456'] = {
                'vms': ['cyris-managed-vm'],
                'disks': ['cyris-managed-disk.qcow2'],
                'networks': []
            }
        
        # Step 2: Create discovery service
        discovery_service = RangeDiscoveryService(mock_settings, orchestrator)
        
        # Step 3: Mock discovery of orphaned resources
        with patch.object(discovery_service, '_discover_virtual_machines') as mock_vms, \
             patch.object(discovery_service, '_discover_disk_files') as mock_disks, \
             patch.object(discovery_service, '_discover_range_directories') as mock_dirs:
            
            # Mock discovered resources including orphaned ones
            mock_vms.return_value = [
                OrphanedResource("vm", "cyris-managed-vm", state="running"),  # Managed
                OrphanedResource("vm", "cyris-orphaned-vm-1", state="shutoff"),  # Orphaned
                OrphanedResource("vm", "cyris-orphaned-vm-2", state="running")   # Orphaned
            ]
            
            mock_disks.return_value = [
                OrphanedResource("disk", "cyris-managed-disk.qcow2", path="/mock/managed"),  # Managed
                OrphanedResource("disk", "cyris-orphaned-disk-1.qcow2", path="/mock/orphaned1"),  # Orphaned
                OrphanedResource("disk", "cyris-orphaned-disk-2.qcow2", path="/mock/orphaned2")   # Orphaned
            ]
            
            mock_dirs.return_value = [
                OrphanedResource("directory", "456", range_id="456"),  # Managed
                OrphanedResource("directory", "789", range_id="789"),  # Orphaned
                OrphanedResource("directory", "101112", range_id="101112")  # Orphaned
            ]
            
            # Step 4: Discover orphaned resources
            discovery_result = discovery_service.discover_all_ranges()
            
            # Verify orphaned resources are identified
            assert discovery_result['orphaned_vms'] == 2
            assert discovery_result['orphaned_disks'] == 2
            assert discovery_result['orphaned_directories'] == 2
            assert discovery_result['total_orphaned_resources'] == 6
            
            # Verify inferred ranges
            assert '789' in discovery_result['inferred_ranges']
            assert '101112' in discovery_result['inferred_ranges']
        
        # Step 5: Test recovery of missing ranges
        with patch.object(discovery_service, '_discover_range_resources') as mock_discover_resources:
            mock_discover_resources.return_value = {
                'vms': ['cyris-recovered-vm'],
                'disks': ['cyris-recovered-disk.qcow2'],
                'networks': []
            }
            
            # Recover specific ranges
            recovery_result = discovery_service.recover_missing_ranges(
                range_ids=['789'], 
                dry_run=False
            )
            
            # Verify recovery success
            assert recovery_result['ranges_to_recover'] == ['789']
            assert '789' in recovery_result['recovered_ranges']
            assert len(recovery_result['failed_ranges']) == 0
            
            # Verify range was added to orchestrator
            assert '789' in orchestrator._ranges
            assert orchestrator._ranges['789'].status == RangeStatus.ACTIVE
            assert '789' in orchestrator._range_resources
    
    def test_orphaned_resource_cleanup_workflow(self, mock_settings):
        """Test workflow for cleaning up orphaned resources"""
        
        # Step 1: Create orchestrator with managed ranges
        mock_provider = Mock()
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator = RangeOrchestrator(mock_settings, mock_provider)
            
            # Add managed range
            orchestrator._ranges['999'] = RangeMetadata(
                range_id='999',
                name='Keep This Range',
                description='Should not be cleaned up',
                status=RangeStatus.ACTIVE,
                created_at=datetime.now()
            )
            orchestrator._range_resources['999'] = {
                'vms': ['cyris-keep-vm'],
                'disks': ['cyris-keep-disk.qcow2'],
                'networks': []
            }
        
        # Step 2: Create discovery service
        discovery_service = RangeDiscoveryService(mock_settings, orchestrator)
        
        # Step 3: Test dry run cleanup
        with patch.object(discovery_service, '_discover_virtual_machines') as mock_vms, \
             patch.object(discovery_service, '_discover_disk_files') as mock_disks, \
             patch.object(discovery_service, '_discover_range_directories') as mock_dirs:
            
            # Mock orphaned resources
            mock_vms.return_value = [
                OrphanedResource("vm", "cyris-keep-vm", state="running"),  # Should not be cleaned
                OrphanedResource("vm", "cyris-cleanup-vm-1", state="shutoff"),
                OrphanedResource("vm", "cyris-cleanup-vm-2", state="error")
            ]
            
            mock_disks.return_value = [
                OrphanedResource("disk", "cyris-keep-disk.qcow2", path="/mock/keep"),  # Should not be cleaned
                OrphanedResource("disk", "cyris-cleanup-disk-1.qcow2", path="/mock/cleanup1"),
                OrphanedResource("disk", "cyris-cleanup-disk-2.qcow2", path="/mock/cleanup2")
            ]
            
            mock_dirs.return_value = [
                OrphanedResource("directory", "999", range_id="999"),  # Should not be cleaned
                OrphanedResource("directory", "888", range_id="888"),
                OrphanedResource("directory", "777", range_id="777")
            ]
            
            # Test dry run cleanup
            cleanup_result = discovery_service.cleanup_orphaned_resources(dry_run=True)
            
            # Verify dry run results
            assert cleanup_result['dry_run'] is True
            assert cleanup_result['orphaned_vms_found'] == 2  # Excluding managed VM
            assert cleanup_result['orphaned_disks_found'] == 2  # Excluding managed disk
            assert cleanup_result['orphaned_directories_found'] == 2  # Excluding managed dir
            
            # Verify nothing was actually cleaned in dry run
            assert len(cleanup_result['cleaned_vms']) == 0
            assert len(cleanup_result['cleaned_disks']) == 0
            assert len(cleanup_result['cleaned_directories']) == 0
        
        # Step 4: Test actual cleanup
        with patch.object(discovery_service.virsh_client, 'destroy_domain') as mock_destroy, \
             patch.object(discovery_service.virsh_client, 'undefine_domain') as mock_undefine, \
             patch('pathlib.Path.unlink') as mock_unlink, \
             patch('shutil.rmtree') as mock_rmtree:
            
            # Mock the same discovery results
            mock_vms.return_value = [
                OrphanedResource("vm", "cyris-keep-vm", state="running"),
                OrphanedResource("vm", "cyris-cleanup-vm-1", state="shutoff")
            ]
            mock_disks.return_value = [
                OrphanedResource("disk", "cyris-keep-disk.qcow2", path="/mock/keep"),
                OrphanedResource("disk", "cyris-cleanup-disk-1.qcow2", path="/mock/cleanup1")
            ]
            mock_dirs.return_value = [
                OrphanedResource("directory", "999", range_id="999"),
                OrphanedResource("directory", "888", range_id="888", path="/mock/888")
            ]
            
            # Test actual cleanup
            cleanup_result = discovery_service.cleanup_orphaned_resources(dry_run=False)
            
            # Verify actual cleanup results
            assert cleanup_result['dry_run'] is False
            assert len(cleanup_result['cleaned_vms']) == 1
            assert 'cyris-cleanup-vm-1' in cleanup_result['cleaned_vms']
            assert len(cleanup_result['cleaned_disks']) == 1
            assert 'cyris-cleanup-disk-1.qcow2' in cleanup_result['cleaned_disks']
            assert len(cleanup_result['cleaned_directories']) == 1
            assert '888' in cleanup_result['cleaned_directories']
            
            # Verify cleanup methods were called
            mock_destroy.assert_called_with('cyris-cleanup-vm-1')
            mock_undefine.assert_called_with('cyris-cleanup-vm-1')
            mock_unlink.assert_called_once()
            mock_rmtree.assert_called_with('/mock/888')
            
            # Verify managed resources were NOT cleaned
            assert 'cyris-keep-vm' not in cleanup_result['cleaned_vms']
            assert 'cyris-keep-disk.qcow2' not in cleanup_result['cleaned_disks']
            assert '999' not in cleanup_result['cleaned_directories']
    
    def test_range_persistence_across_restarts(self, mock_settings, temp_cyber_range_dir):
        """Test that range data persists across orchestrator restarts"""
        mock_provider = Mock()
        
        # Step 1: Create first orchestrator instance and add range
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator1 = RangeOrchestrator(mock_settings, mock_provider)
            
            # Add range data
            orchestrator1._ranges['persistent_range'] = RangeMetadata(
                range_id='persistent_range',
                name='Persistent Test Range',
                description='Should survive restart',
                status=RangeStatus.ACTIVE,
                created_at=datetime.now()
            )
            orchestrator1._range_resources['persistent_range'] = {
                'vms': ['cyris-persistent-vm'],
                'disks': ['cyris-persistent-disk.qcow2'],
                'networks': ['cyris-persistent-network']
            }
            
            # Save data
            orchestrator1._save_persistent_data()
        
        # Step 2: Create second orchestrator instance (simulates restart)
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator2 = RangeOrchestrator(mock_settings, mock_provider)
            
            # Step 3: Verify data was loaded
            assert 'persistent_range' in orchestrator2._ranges
            assert orchestrator2._ranges['persistent_range'].name == 'Persistent Test Range'
            assert orchestrator2._ranges['persistent_range'].status == RangeStatus.ACTIVE
            
            assert 'persistent_range' in orchestrator2._range_resources
            resources = orchestrator2._range_resources['persistent_range']
            assert 'cyris-persistent-vm' in resources['vms']
            assert 'cyris-persistent-disk.qcow2' in resources['disks']
            assert 'cyris-persistent-network' in resources['networks']
        
        # Step 3: Create discovery service and verify tracking is maintained
        discovery_service = RangeDiscoveryService(mock_settings, orchestrator2)
        
        with patch.object(discovery_service, '_discover_virtual_machines') as mock_vms:
            mock_vms.return_value = [
                OrphanedResource("vm", "cyris-persistent-vm", state="running")
            ]
            
            # Should not identify as orphaned because it's properly tracked
            orphaned_vms = discovery_service._identify_orphaned_vms(
                mock_vms.return_value, 
                set(orchestrator2._ranges.keys())
            )
            
            assert len(orphaned_vms) == 0  # Should be empty because VM is tracked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])