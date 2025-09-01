"""
Integration tests for real VM IP assignment functionality.
Tests the complete workflow with actual VM creation and IP discovery.
"""

import pytest
import tempfile
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.cyris.services.orchestrator import RangeOrchestrator
from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
from src.cyris.config.settings import CyRISSettings
from src.cyris.tools.vm_ip_manager import get_vm_ip_simple, VMIPManager


class TestRealVMIPAssignmentIntegration:
    """Integration tests for VM IP assignment with real libvirt operations"""
    
    @pytest.fixture
    def settings(self):
        """Create test settings with temporary directories"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = CyRISSettings()
            settings.cyber_range_dir = Path(temp_dir)
            yield settings
    
    @pytest.fixture
    def kvm_provider(self, settings):
        """Create KVM provider for integration testing"""
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': str(settings.cyber_range_dir),
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        return KVMProvider(kvm_config)
    
    @pytest.fixture
    def orchestrator(self, settings, kvm_provider):
        """Create orchestrator for integration testing"""
        return RangeOrchestrator(settings, kvm_provider)
    
    @pytest.fixture
    def vm_ip_manager(self):
        """Create VM IP manager for testing"""
        return VMIPManager()
    
    def test_bootable_base_image_creation_integration(self, kvm_provider):
        """Test that bootable base images are created correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_image_path = Path(temp_dir) / "test_base.qcow2"
            
            # Test base image creation (with mocked download for CI)
            with patch('urllib.request.urlretrieve') as mock_download, \
                 patch('subprocess.run') as mock_subprocess:
                
                # Mock successful download
                mock_download.return_value = None
                mock_subprocess.return_value = MagicMock(returncode=0)
                
                kvm_provider._ensure_bootable_base_image(base_image_path)
                
                # Verify download was called
                mock_download.assert_called_once()
                
                # Verify qemu-img commands were called
                expected_calls = 2  # convert and resize
                assert mock_subprocess.call_count == expected_calls
    
    def test_cloud_init_config_creation_integration(self, kvm_provider):
        """Test that cloud-init configuration is created correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            disk_dir = Path(temp_dir)
            
            # Create cloud-init configuration
            kvm_provider._create_cloud_init_config(disk_dir)
            
            # Verify files were created
            cloud_init_dir = disk_dir / "cloud-init"
            assert cloud_init_dir.exists()
            assert (cloud_init_dir / "user-data").exists()
            assert (cloud_init_dir / "network-config").exists()
            assert (cloud_init_dir / "meta-data").exists()
            
            # Verify file contents
            user_data = (cloud_init_dir / "user-data").read_text()
            assert "#cloud-config" in user_data
            assert "name: ubuntu" in user_data
            assert "package_update: true" in user_data
            
            network_config = (cloud_init_dir / "network-config").read_text()
            assert "version: 2" in network_config
            assert "dhcp4: true" in network_config
    
    def test_ip_discovery_integration_with_mocked_vm(self, vm_ip_manager):
        """Test IP discovery integration with mocked VM responses"""
        test_vm_name = "cyris-test-integration"
        
        # Test DHCP lease discovery
        dhcp_output = f"""
 Expiry Time           MAC address         Protocol   IP address           Hostname     Client ID or DUID
--------------------------------------------------------------------------------------------------------------------------------------------------
 2025-09-01 16:40:33   52:54:00:2b:06:c8   ipv4       192.168.122.100/24   {test_vm_name}  client-id
"""
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = dhcp_output
            mock_run.return_value = mock_result
            
            ip, error = get_vm_ip_simple(test_vm_name)
            
            assert ip == "192.168.122.100"
            assert error is None
    
    def test_ip_discovery_fallback_chain_integration(self, vm_ip_manager):
        """Test the complete IP discovery fallback chain"""
        test_vm_name = "cyris-test-fallback"
        
        # Mock DHCP leases failure, virsh success
        with patch('subprocess.run') as mock_run:
            def side_effect(cmd, **kwargs):
                if 'net-dhcp-leases' in cmd:
                    # DHCP leases returns empty
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "No leases found"
                    return result
                elif 'domifaddr' in cmd:
                    # virsh domifaddr succeeds
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = f"""
 Name       MAC address          Protocol     Address
-------------------------------------------------------------------------------
 vnet0      52:54:00:2b:06:c8    ipv4         192.168.122.150/24
"""
                    return result
                else:
                    result = MagicMock()
                    result.returncode = 1
                    return result
            
            mock_run.side_effect = side_effect
            
            ip, error = get_vm_ip_simple(test_vm_name)
            
            assert ip == "192.168.122.150"
            assert error is None
    
    def test_ip_discovery_failure_with_diagnostics_integration(self, vm_ip_manager):
        """Test IP discovery failure with diagnostic information"""
        test_vm_name = "cyris-test-failed"
        
        with patch('subprocess.run') as mock_run:
            def side_effect(cmd, **kwargs):
                if 'net-dhcp-leases' in cmd or 'domifaddr' in cmd:
                    # Both IP discovery methods fail
                    result = MagicMock()
                    result.returncode = 1
                    result.stdout = "Command failed"
                    return result
                elif 'domstate' in cmd:
                    # VM status check
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "running"
                    return result
                elif 'dumpxml' in cmd:
                    # VM XML check (has interface)
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "<domain><interface type='network'></interface></domain>"
                    return result
                else:
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "2 active leases"
                    return result
            
            mock_run.side_effect = side_effect
            
            ip, error = get_vm_ip_simple(test_vm_name)
            
            assert ip is None
            assert error is not None
            assert "VM Status: running" in error
            assert "Network Interface: present" in error
    
    def test_orchestrator_vm_creation_with_ip_discovery_integration(self, orchestrator):
        """Test orchestrator VM creation with IP discovery integration"""
        test_range_id = "test-integration"
        
        # Mock guest and host objects
        mock_guest = MagicMock()
        mock_guest.guest_id = "test-vm"
        mock_guest.tasks = []
        
        mock_host = MagicMock()
        mock_host.host_id = "test-host"
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch.object(orchestrator, '_get_vm_ip_by_name') as mock_get_ip:
            
            # Mock successful VM creation
            mock_create_hosts.return_value = ["host-1"]
            mock_create_guests.return_value = ["cyris-test-vm-abc123"]
            mock_get_ip.return_value = "192.168.122.200"
            
            # Create range
            result = orchestrator.create_range(
                range_id=test_range_id,
                name="Test Integration Range",
                description="Integration test range",
                hosts=[mock_host],
                guests=[mock_guest]
            )
            
            # Verify range creation
            assert result.range_id == test_range_id
            assert result.status.value == "active"
            
            # Verify VM IP discovery was called
            mock_get_ip.assert_called_once_with("cyris-test-vm-abc123", max_wait_minutes=1)
    
    def test_range_status_with_real_ip_discovery_integration(self, orchestrator):
        """Test range status reporting with real IP discovery integration"""
        test_range_id = "test-status-integration"
        
        # Create a test range with mocked VMs
        orchestrator._ranges[test_range_id] = MagicMock()
        orchestrator._ranges[test_range_id].range_id = test_range_id
        orchestrator._ranges[test_range_id].name = "Test Status Range"
        orchestrator._ranges[test_range_id].description = "Test range for status integration"
        orchestrator._ranges[test_range_id].status.value = "active"
        orchestrator._ranges[test_range_id].created_at.isoformat.return_value = "2025-09-01T12:00:00"
        orchestrator._ranges[test_range_id].last_modified.isoformat.return_value = "2025-09-01T12:00:00"
        
        orchestrator._range_resources[test_range_id] = {
            "guests": ["cyris-status-test-vm"]
        }
        
        with patch('src.cyris.tools.vm_ip_manager.get_vm_ip_simple') as mock_get_ip, \
             patch.object(orchestrator.provider, 'get_status') as mock_get_status, \
             patch.object(orchestrator.ssh_manager, 'create_from_vm_info') as mock_create_ssh, \
             patch.object(orchestrator.ssh_manager, 'verify_connectivity') as mock_verify:
            
            # Mock successful IP discovery and SSH
            mock_get_ip.return_value = ("192.168.122.201", None)
            mock_get_status.return_value = {"cyris-status-test-vm": "running"}
            mock_verify.return_value = {"auth_working": True}
            
            # Get detailed status
            status = orchestrator.get_range_status_detailed(test_range_id)
            
            # Verify status structure
            assert status is not None
            assert status["range_id"] == test_range_id
            assert status["status"] == "active"
            assert len(status["vms"]) == 1
            
            vm_info = status["vms"][0]
            assert vm_info["name"] == "cyris-status-test-vm"
            assert vm_info["ip"] == "192.168.122.201"
            assert vm_info["status"] == "running"
            assert vm_info["ssh_accessible"] is True
            assert vm_info["error_details"] is None
    
    def test_vm_lifecycle_with_ip_assignment_integration(self, kvm_provider):
        """Test complete VM lifecycle with IP assignment integration"""
        test_vm_name = "cyris-lifecycle-test"
        
        with patch.object(kvm_provider, '_ensure_bootable_base_image'), \
             patch.object(kvm_provider, '_create_vm_disk') as mock_create_disk, \
             patch('subprocess.run') as mock_run:
            
            # Mock successful VM operations
            mock_create_disk.return_value = f"/tmp/{test_vm_name}.qcow2"
            mock_run.return_value = MagicMock(returncode=0)
            
            # Mock guest object
            mock_guest = MagicMock()
            mock_guest.guest_id = "lifecycle-test"
            mock_guest.basevm_config_file = None
            
            # Create VM (mocked)
            created_vm = kvm_provider._create_vm_disk(test_vm_name, mock_guest)
            
            # Verify VM disk creation
            assert test_vm_name in created_vm
    
    def test_error_recovery_integration(self, orchestrator):
        """Test error recovery and cleanup integration"""
        test_range_id = "test-error-recovery"
        
        mock_host = MagicMock()
        mock_host.host_id = "error-test-host"
        
        mock_guest = MagicMock()
        mock_guest.guest_id = "error-test-vm"
        mock_guest.tasks = []
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch.object(orchestrator, '_cleanup_range_resources') as mock_cleanup:
            
            # Mock host creation success, guest creation failure
            mock_create_hosts.return_value = ["host-1"]
            mock_create_guests.side_effect = Exception("Guest creation failed")
            
            # Attempt range creation
            with pytest.raises(Exception):
                orchestrator.create_range(
                    range_id=test_range_id,
                    name="Error Recovery Test",
                    description="Test error recovery",
                    hosts=[mock_host],
                    guests=[mock_guest]
                )
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once_with(test_range_id)


class TestVMIPManagerIntegration:
    """Integration tests specifically for VMIPManager functionality"""
    
    @pytest.fixture
    def vm_ip_manager(self):
        """Create VM IP manager for testing"""
        return VMIPManager()
    
    def test_vm_health_info_integration(self, vm_ip_manager):
        """Test VM health information collection integration"""
        test_vm_name = "cyris-health-test"
        
        with patch.object(vm_ip_manager, 'connection', None), \
             patch('subprocess.run') as mock_run:
            
            def side_effect(cmd, **kwargs):
                if 'domstate' in cmd:
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "running"
                    return result
                elif 'domuuid' in cmd:
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "12345678-1234-1234-1234-123456789abc"
                    return result
                elif 'dumpxml' in cmd:
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = """<domain>
                        <devices>
                            <disk type='file' device='disk'>
                                <source file='/tmp/test.qcow2'/>
                            </disk>
                        </devices>
                    </domain>"""
                    return result
                elif 'qemu-img' in cmd and 'info' in cmd:
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = "virtual size: 10G"
                    return result
                else:
                    result = MagicMock()
                    result.returncode = 1
                    return result
            
            mock_run.side_effect = side_effect
            
            # Get health info using virsh fallback
            health_info = vm_ip_manager.get_vm_health_info(test_vm_name)
            
            # Verify health info structure
            assert health_info.vm_name == test_vm_name
            assert health_info.vm_id == "12345678-1234-1234-1234-123456789abc"
            assert health_info.libvirt_status == "running"
            assert health_info.disk_path == "/tmp/test.qcow2"
    
    def test_multiple_vm_ip_discovery_integration(self, vm_ip_manager):
        """Test discovering IPs for multiple VMs integration"""
        test_vms = ["cyris-vm1", "cyris-vm2", "cyris-vm3"]
        
        with patch.object(vm_ip_manager, 'get_vm_ip_addresses') as mock_get_ip:
            
            def side_effect(vm_name):
                if vm_name == "cyris-vm1":
                    return MagicMock(ip_addresses=["192.168.122.101"])
                elif vm_name == "cyris-vm2":
                    return MagicMock(ip_addresses=["192.168.122.102"])
                else:
                    return None
            
            mock_get_ip.side_effect = side_effect
            
            # Get all VM IPs
            result = vm_ip_manager.get_all_vm_ips(test_vms)
            
            # Verify results
            assert len(result) == 2  # Only 2 VMs found IPs
            assert "cyris-vm1" in result
            assert "cyris-vm2" in result
            assert "cyris-vm3" not in result
    
    def test_ip_cache_integration(self, vm_ip_manager):
        """Test IP caching functionality integration"""
        test_vm_name = "cyris-cache-test"
        
        # Mock VM info
        mock_vm_info = MagicMock()
        mock_vm_info.ip_addresses = ["192.168.122.150"]
        
        with patch.object(vm_ip_manager, '_get_ips_via_libvirt') as mock_libvirt:
            mock_libvirt.return_value = mock_vm_info
            
            # First call - should hit libvirt method
            result1 = vm_ip_manager.get_vm_ip_addresses(test_vm_name)
            
            # Second call - should use cache
            result2 = vm_ip_manager.get_cached_ip_info(test_vm_name, max_age_seconds=600)
            
            # Verify caching behavior
            assert result1 == mock_vm_info
            assert result2 == mock_vm_info
            mock_libvirt.assert_called_once()  # Only called once due to caching


if __name__ == "__main__":
    pytest.main([__file__, "-v"])