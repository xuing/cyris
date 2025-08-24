"""
Test cases for RangeDiscoveryService - resource discovery and cleanup functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from cyris.services.range_discovery import RangeDiscoveryService, OrphanedResource
from cyris.services.orchestrator import RangeOrchestrator, RangeMetadata, RangeStatus
from cyris.config.settings import CyRISSettings


class TestRangeDiscoveryService:
    """Test cases for range discovery functionality"""

    @pytest.fixture
    def mock_settings(self):
        """Mock CyRIS settings"""
        settings = Mock(spec=CyRISSettings)
        settings.cyber_range_dir = "/mock/cyber_range"
        settings.cyris_path = Path("/mock/cyris")
        return settings

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator with sample ranges"""
        orchestrator = Mock(spec=RangeOrchestrator)
        # Mock managed ranges
        orchestrator._ranges = {
            "123": RangeMetadata(
                range_id="123",
                name="Range 123",
                description="Active range",
                status=RangeStatus.ACTIVE,
                created_at=datetime.now()
            )
        }
        orchestrator._range_resources = {
            "123": {
                "vms": ["cyris-managed-vm-123"],
                "disks": ["cyris-managed-disk-123.qcow2"],
                "networks": []
            }
        }
        orchestrator._save_persistent_data = Mock()
        return orchestrator

    @pytest.fixture
    def mock_virsh_client(self):
        """Mock virsh client"""
        with patch('cyris.services.range_discovery.VirshLibvirt') as mock_class:
            mock_client = Mock()
            mock_client.list_all_domains.return_value = [
                {"name": "cyris-managed-vm-123", "state": "running"},
                {"name": "cyris-orphaned-uuid-456", "state": "shutoff"},
                {"name": "cyris-desktop-789", "state": "running"},
                {"name": "regular-vm", "state": "running"}  # Non-CyRIS VM
            ]
            mock_client.destroy_domain = Mock()
            mock_client.undefine_domain = Mock()
            mock_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def discovery_service(self, mock_settings, mock_orchestrator, mock_virsh_client):
        """Create discovery service instance"""
        return RangeDiscoveryService(mock_settings, mock_orchestrator)

    def test_discover_virtual_machines(self, discovery_service, mock_virsh_client):
        """Test discovery of virtual machines"""
        # Test discovery
        vms = discovery_service._discover_virtual_machines()
        
        # Verify results
        assert len(vms) == 3  # Only CyRIS VMs
        vm_names = [vm.name for vm in vms]
        assert "cyris-managed-vm-123" in vm_names
        assert "cyris-orphaned-uuid-456" in vm_names
        assert "cyris-desktop-789" in vm_names
        assert "regular-vm" not in vm_names
        
        # Verify resource properties
        for vm in vms:
            assert vm.resource_type == "vm"
            assert vm.name.startswith("cyris-")

    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.stat')
    def test_discover_disk_files(self, mock_stat, mock_glob, discovery_service):
        """Test discovery of disk files"""
        # Mock disk files
        mock_disk1 = Mock()
        mock_disk1.name = "cyris-managed-disk-123.qcow2"
        mock_disk1.stat.return_value.st_size = 1024000
        mock_disk1.stat.return_value.st_ctime = 1634567890
        
        mock_disk2 = Mock()
        mock_disk2.name = "cyris-orphaned-disk-456.qcow2" 
        mock_disk2.stat.return_value.st_size = 2048000
        mock_disk2.stat.return_value.st_ctime = 1634567900
        
        mock_disk3 = Mock()
        mock_disk3.name = "regular-disk.qcow2"  # Non-CyRIS disk
        
        mock_glob.return_value = [mock_disk1, mock_disk2, mock_disk3]
        
        # Test discovery
        disks = discovery_service._discover_disk_files()
        
        # Verify results
        assert len(disks) == 2  # Only CyRIS disks
        disk_names = [disk.name for disk in disks]
        assert "cyris-managed-disk-123.qcow2" in disk_names
        assert "cyris-orphaned-disk-456.qcow2" in disk_names
        assert "regular-disk.qcow2" not in disk_names

    @patch('pathlib.Path.iterdir')
    def test_discover_range_directories(self, mock_iterdir, discovery_service):
        """Test discovery of range directories"""
        # Mock directories
        mock_dir1 = Mock()
        mock_dir1.name = "123"
        mock_dir1.is_dir.return_value = True
        mock_dir1.stat.return_value.st_ctime = 1634567890
        
        mock_dir2 = Mock()
        mock_dir2.name = "456"
        mock_dir2.is_dir.return_value = True
        mock_dir2.stat.return_value.st_ctime = 1634567900
        
        mock_dir3 = Mock()
        mock_dir3.name = "logs"  # Non-numeric directory
        mock_dir3.is_dir.return_value = True
        
        mock_file = Mock()
        mock_file.name = "789"
        mock_file.is_dir.return_value = False  # File, not directory
        
        mock_iterdir.return_value = [mock_dir1, mock_dir2, mock_dir3, mock_file]
        
        # Test discovery
        directories = discovery_service._discover_range_directories()
        
        # Verify results
        assert len(directories) == 2  # Only numeric directories
        dir_names = [dir.name for dir in directories]
        assert "123" in dir_names
        assert "456" in dir_names
        assert "logs" not in dir_names

    def test_identify_orphaned_vms(self, discovery_service, mock_orchestrator):
        """Test identification of orphaned VMs"""
        # Create test VMs
        managed_vm = OrphanedResource("vm", "cyris-managed-vm-123", state="running")
        orphaned_vm1 = OrphanedResource("vm", "cyris-orphaned-uuid-456", state="shutoff")
        orphaned_vm2 = OrphanedResource("vm", "cyris-desktop-789", state="running")
        
        vms = [managed_vm, orphaned_vm1, orphaned_vm2]
        managed_ranges = {"123"}
        
        # Test identification
        orphaned = discovery_service._identify_orphaned_vms(vms, managed_ranges)
        
        # Verify results
        assert len(orphaned) == 2
        orphaned_names = [vm.name for vm in orphaned]
        assert "cyris-orphaned-uuid-456" in orphaned_names
        assert "cyris-desktop-789" in orphaned_names
        assert "cyris-managed-vm-123" not in orphaned_names

    def test_identify_orphaned_directories(self, discovery_service):
        """Test identification of orphaned directories"""
        # Create test directories
        managed_dir = OrphanedResource("directory", "123", range_id="123")
        orphaned_dir1 = OrphanedResource("directory", "456", range_id="456")
        orphaned_dir2 = OrphanedResource("directory", "789", range_id="789")
        
        directories = [managed_dir, orphaned_dir1, orphaned_dir2]
        managed_ranges = {"123"}
        
        # Test identification
        orphaned = discovery_service._identify_orphaned_directories(directories, managed_ranges)
        
        # Verify results
        assert len(orphaned) == 2
        orphaned_names = [dir.name for dir in orphaned]
        assert "456" in orphaned_names
        assert "789" in orphaned_names
        assert "123" not in orphaned_names

    @patch.object(RangeDiscoveryService, '_discover_virtual_machines')
    @patch.object(RangeDiscoveryService, '_discover_disk_files')
    @patch.object(RangeDiscoveryService, '_discover_range_directories')
    def test_discover_all_ranges(self, mock_dirs, mock_disks, mock_vms, discovery_service):
        """Test comprehensive range discovery"""
        # Mock discovery results
        mock_vms.return_value = [
            OrphanedResource("vm", "cyris-vm-1"),
            OrphanedResource("vm", "cyris-vm-2")
        ]
        mock_disks.return_value = [
            OrphanedResource("disk", "cyris-disk-1.qcow2")
        ]
        mock_dirs.return_value = [
            OrphanedResource("directory", "456", range_id="456"),
            OrphanedResource("directory", "789", range_id="789")
        ]
        
        # Test discovery
        result = discovery_service.discover_all_ranges()
        
        # Verify results
        assert result["discovered_vms"] == 2
        assert result["discovered_disks"] == 1
        assert result["discovered_directories"] == 2
        assert result["orphaned_vms"] == 2  # Both VMs are orphaned
        assert result["orphaned_disks"] == 1  # Disk is orphaned
        assert result["orphaned_directories"] == 2  # Both dirs are orphaned
        assert "456" in result["inferred_ranges"]
        assert "789" in result["inferred_ranges"]

    @patch.object(RangeDiscoveryService, 'discover_all_ranges')
    @patch.object(RangeDiscoveryService, '_discover_range_directories')
    def test_recover_missing_ranges(self, mock_dirs, mock_discover, discovery_service, mock_orchestrator):
        """Test recovery of missing ranges"""
        # Mock discovery results
        mock_discover.return_value = {"orphaned_directories": 2}
        mock_dirs.return_value = [
            OrphanedResource("directory", "456", range_id="456", created_time=datetime.now()),
            OrphanedResource("directory", "789", range_id="789", created_time=datetime.now())
        ]
        
        # Mock resource discovery for specific range
        discovery_service._discover_range_resources = Mock(return_value={
            "vms": ["cyris-vm-456"],
            "disks": ["cyris-disk-456.qcow2"],
            "networks": []
        })
        
        # Test recovery (not dry run)
        result = discovery_service.recover_missing_ranges(dry_run=False)
        
        # Verify results
        assert len(result["recovered_ranges"]) == 2
        assert "456" in result["recovered_ranges"]
        assert "789" in result["recovered_ranges"]
        assert len(result["failed_ranges"]) == 0
        
        # Verify orchestrator was updated
        assert mock_orchestrator._save_persistent_data.called

    @patch.object(RangeDiscoveryService, '_discover_virtual_machines')
    @patch.object(RangeDiscoveryService, '_discover_disk_files')
    @patch.object(RangeDiscoveryService, '_discover_range_directories')
    def test_cleanup_orphaned_resources_dry_run(self, mock_dirs, mock_disks, mock_vms, 
                                               discovery_service, mock_virsh_client):
        """Test cleanup of orphaned resources in dry run mode"""
        # Mock orphaned resources
        orphaned_vm = OrphanedResource("vm", "cyris-orphaned-vm")
        orphaned_disk = OrphanedResource("disk", "cyris-orphaned-disk.qcow2", path="/mock/path/disk.qcow2")
        orphaned_dir = OrphanedResource("directory", "456", path="/mock/path/456")
        
        mock_vms.return_value = [orphaned_vm]
        mock_disks.return_value = [orphaned_disk]
        mock_dirs.return_value = [orphaned_dir]
        
        # Test dry run cleanup
        result = discovery_service.cleanup_orphaned_resources(dry_run=True)
        
        # Verify no actual cleanup happened
        assert not mock_virsh_client.destroy_domain.called
        assert not mock_virsh_client.undefine_domain.called
        
        # But resources were identified
        assert result["orphaned_vms_found"] == 1
        assert result["orphaned_disks_found"] == 1
        assert result["orphaned_directories_found"] == 1

    @patch.object(RangeDiscoveryService, '_discover_virtual_machines')
    @patch('pathlib.Path.unlink')
    @patch('shutil.rmtree')
    def test_cleanup_orphaned_resources_actual(self, mock_rmtree, mock_unlink, mock_vms, 
                                             discovery_service, mock_virsh_client):
        """Test actual cleanup of orphaned resources"""
        # Mock orphaned VM
        orphaned_vm = OrphanedResource("vm", "cyris-orphaned-vm")
        mock_vms.return_value = [orphaned_vm]
        
        # Mock other discovery methods to return empty lists
        discovery_service._discover_disk_files = Mock(return_value=[])
        discovery_service._discover_range_directories = Mock(return_value=[])
        
        # Test actual cleanup
        result = discovery_service.cleanup_orphaned_resources(
            resource_types=["vms"], 
            dry_run=False
        )
        
        # Verify cleanup happened
        mock_virsh_client.destroy_domain.assert_called_once_with("cyris-orphaned-vm")
        mock_virsh_client.undefine_domain.assert_called_once_with("cyris-orphaned-vm")
        
        # Verify results
        assert len(result["cleaned_vms"]) == 1
        assert "cyris-orphaned-vm" in result["cleaned_vms"]
        assert len(result["failed_cleanups"]) == 0

    def test_cleanup_error_handling(self, discovery_service, mock_virsh_client):
        """Test error handling during cleanup"""
        # Mock virsh client to raise exception
        mock_virsh_client.destroy_domain.side_effect = Exception("Cleanup failed")
        
        orphaned_vm = OrphanedResource("vm", "cyris-problematic-vm")
        discovery_service._discover_virtual_machines = Mock(return_value=[orphaned_vm])
        discovery_service._discover_disk_files = Mock(return_value=[])
        discovery_service._discover_range_directories = Mock(return_value=[])
        
        # Test cleanup with error
        result = discovery_service.cleanup_orphaned_resources(
            resource_types=["vms"],
            dry_run=False
        )
        
        # Verify error was handled
        assert len(result["failed_cleanups"]) == 1
        assert result["failed_cleanups"][0]["resource"] == "cyris-problematic-vm"
        assert result["failed_cleanups"][0]["type"] == "vm"
        assert "Cleanup failed" in result["failed_cleanups"][0]["error"]


class TestOrphanedResource:
    """Test cases for OrphanedResource dataclass"""
    
    def test_orphaned_resource_creation(self):
        """Test creating OrphanedResource instances"""
        # Test basic creation
        resource = OrphanedResource("vm", "cyris-test-vm")
        assert resource.resource_type == "vm"
        assert resource.name == "cyris-test-vm"
        assert resource.path is None
        assert resource.state is None
        
        # Test full creation
        created_time = datetime.now()
        resource = OrphanedResource(
            resource_type="disk",
            name="cyris-test-disk.qcow2",
            path="/path/to/disk.qcow2",
            state="available",
            created_time=created_time,
            size=1024000,
            range_id="123"
        )
        assert resource.resource_type == "disk"
        assert resource.name == "cyris-test-disk.qcow2"
        assert resource.path == "/path/to/disk.qcow2"
        assert resource.state == "available"
        assert resource.created_time == created_time
        assert resource.size == 1024000
        assert resource.range_id == "123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])