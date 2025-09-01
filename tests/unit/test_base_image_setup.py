"""
Unit tests for automated base image setup functionality.
Tests the bootable image creation and cloud-init configuration.
"""

import pytest
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call

from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
from src.cyris.config.settings import CyRISSettings


class TestBootableBaseImageSetup:
    """Test bootable base image setup functionality"""
    
    @pytest.fixture
    def kvm_provider(self):
        """Create KVM provider instance for testing"""
        settings = CyRISSettings()
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': str(settings.cyber_range_dir),
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        return KVMProvider(kvm_config)
    
    @pytest.fixture
    def temp_image_path(self):
        """Create temporary image path for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "test_base.qcow2"
    
    def test_ensure_bootable_base_image_success(self, kvm_provider, temp_image_path):
        """Test successful base image creation"""
        temp_file_name = "/tmp/downloaded_image.img"
        mock_temp_file = MagicMock()
        mock_temp_file.name = temp_file_name
        mock_temp_file.__enter__ = MagicMock(return_value=mock_temp_file)
        mock_temp_file.__exit__ = MagicMock(return_value=None)
        
        with patch('tempfile.NamedTemporaryFile', return_value=mock_temp_file), \
             patch('urllib.request.urlretrieve') as mock_download, \
             patch('subprocess.run') as mock_subprocess, \
             patch.object(kvm_provider, '_create_cloud_init_config') as mock_cloud_init:
            
            mock_subprocess.return_value = MagicMock(returncode=0)
            
            kvm_provider._ensure_bootable_base_image(temp_image_path)
            
            # Verify download was called with the temp file name
            mock_download.assert_called_once_with(
                "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
                temp_file_name
            )
            
            # Verify qemu-img commands were called
            expected_calls = [
                call([
                    "qemu-img", "convert", "-f", "qcow2", "-O", "qcow2",
                    temp_file_name, str(temp_image_path)
                ], check=True),
                call([
                    "qemu-img", "resize", str(temp_image_path), "10G"
                ], check=True)
            ]
            mock_subprocess.assert_has_calls(expected_calls)
            
            # Verify cloud-init config creation
            mock_cloud_init.assert_called_once_with(temp_image_path.parent)
    
    def test_ensure_bootable_base_image_download_failure(self, kvm_provider, temp_image_path):
        """Test fallback when download fails"""
        with patch('tempfile.NamedTemporaryFile'), \
             patch('urllib.request.urlretrieve', side_effect=Exception("Download failed")), \
             patch('subprocess.run') as mock_subprocess:
            
            mock_subprocess.return_value = MagicMock(returncode=0)
            
            kvm_provider._ensure_bootable_base_image(temp_image_path)
            
            # Should fall back to creating empty image
            mock_subprocess.assert_called_with([
                "qemu-img", "create", "-f", "qcow2", 
                str(temp_image_path), "10G"
            ], check=True)
    
    def test_ensure_bootable_base_image_convert_failure(self, kvm_provider, temp_image_path):
        """Test fallback when qemu-img convert fails"""
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/downloaded_image.img"
        
        with patch('tempfile.NamedTemporaryFile', return_value=mock_temp_file), \
             patch('urllib.request.urlretrieve') as mock_download, \
             patch('subprocess.run') as mock_subprocess:
            
            # First call (convert) fails, second call (fallback create) succeeds
            mock_subprocess.side_effect = [
                subprocess.CalledProcessError(1, "qemu-img convert"),
                MagicMock(returncode=0)  # Fallback create succeeds
            ]
            
            kvm_provider._ensure_bootable_base_image(temp_image_path)
            
            # Verify fallback to empty image creation
            assert mock_subprocess.call_count == 2
            fallback_call = mock_subprocess.call_args_list[1]
            assert "qemu-img" in fallback_call[0][0]
            assert "create" in fallback_call[0][0]


class TestCloudInitConfiguration:
    """Test cloud-init configuration creation"""
    
    @pytest.fixture
    def kvm_provider(self):
        """Create KVM provider instance for testing"""
        settings = CyRISSettings()
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': str(settings.cyber_range_dir),
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        return KVMProvider(kvm_config)
    
    @pytest.fixture  
    def temp_disk_dir(self):
        """Create temporary disk directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_create_cloud_init_config(self, kvm_provider, temp_disk_dir):
        """Test cloud-init configuration file creation"""
        kvm_provider._create_cloud_init_config(temp_disk_dir)
        
        cloud_init_dir = temp_disk_dir / "cloud-init"
        
        # Verify directory creation
        assert cloud_init_dir.exists()
        assert cloud_init_dir.is_dir()
        
        # Verify user-data file
        user_data_file = cloud_init_dir / "user-data"
        assert user_data_file.exists()
        
        user_data_content = user_data_file.read_text()
        assert "#cloud-config" in user_data_content
        assert "name: ubuntu" in user_data_content
        assert "package_update: true" in user_data_content
        assert "systemd-networkd" in user_data_content
        
        # Verify network-config file
        network_config_file = cloud_init_dir / "network-config"
        assert network_config_file.exists()
        
        network_content = network_config_file.read_text()
        assert "version: 2" in network_content
        assert "dhcp4: true" in network_content
        assert "dhcp-identifier: mac" in network_content
        
        # Verify meta-data file
        meta_data_file = cloud_init_dir / "meta-data"
        assert meta_data_file.exists()
        
        meta_data_content = meta_data_file.read_text()
        assert "instance-id: cyris-vm" in meta_data_content
    
    def test_cloud_init_config_directory_exists(self, kvm_provider, temp_disk_dir):
        """Test cloud-init config when directory already exists"""
        cloud_init_dir = temp_disk_dir / "cloud-init"
        cloud_init_dir.mkdir()
        
        # Should not fail if directory exists
        kvm_provider._create_cloud_init_config(temp_disk_dir)
        
        assert cloud_init_dir.exists()
        assert (cloud_init_dir / "user-data").exists()
    
    def test_cloud_init_user_data_format(self, kvm_provider, temp_disk_dir):
        """Test user-data format and content"""
        kvm_provider._create_cloud_init_config(temp_disk_dir)
        
        user_data_file = temp_disk_dir / "cloud-init" / "user-data"
        content = user_data_file.read_text()
        
        # Check required cloud-config sections
        assert content.startswith("#cloud-config")
        assert "users:" in content
        assert "package_update:" in content
        assert "packages:" in content
        assert "runcmd:" in content
        
        # Check user configuration
        assert "name: ubuntu" in content
        assert "sudo: ALL=(ALL) NOPASSWD:ALL" in content
        assert "shell: /bin/bash" in content
        
        # Check networking setup commands
        assert "systemctl enable systemd-networkd" in content
        assert "systemctl start systemd-networkd" in content
    
    def test_cloud_init_network_config_format(self, kvm_provider, temp_disk_dir):
        """Test network-config format and content"""
        kvm_provider._create_cloud_init_config(temp_disk_dir)
        
        network_file = temp_disk_dir / "cloud-init" / "network-config"
        content = network_file.read_text()
        
        # Check network configuration structure
        assert "version: 2" in content
        assert "ethernets:" in content
        assert "eth0:" in content
        assert "dhcp4: true" in content
        assert "dhcp-identifier: mac" in content


class TestBaseImageIntegration:
    """Integration tests for base image functionality"""
    
    @pytest.fixture
    def kvm_provider(self):
        """Create KVM provider instance for testing"""
        settings = CyRISSettings()
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': str(settings.cyber_range_dir),
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        return KVMProvider(kvm_config)
    
    def test_vm_disk_creation_with_bootable_base(self, kvm_provider):
        """Test VM disk creation using bootable base image"""
        vm_name = "test-vm-bootable"
        
        # Mock guest object
        mock_guest = MagicMock()
        mock_guest.guest_id = "test-guest"
        mock_guest.basevm_config_file = None  # No specific base VM
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock range context
            kvm_provider._current_range_id = "test_range"
            
            with patch.object(kvm_provider, '_ensure_bootable_base_image') as mock_ensure_base, \
                 patch('subprocess.run') as mock_subprocess, \
                 patch('pathlib.Path.stat') as mock_stat:
                
                # Mock substantial base image (> 1024 bytes)
                mock_stat.return_value.st_size = 1000000  # 1MB
                mock_subprocess.return_value = MagicMock(returncode=0)
                
                # Set up paths as they would be in real scenario
                base_path = temp_path / "base.qcow2"
                base_path.touch()  # Create file
                
                # Mock the settings directory by patching the create_vm_disk method's path logic
                with patch.object(kvm_provider, 'base_image_dir', temp_path):
                    disk_path = kvm_provider._create_vm_disk(vm_name, mock_guest)
                
                # Verify base image setup was called
                mock_ensure_base.assert_called_once()
                
                # Verify COW overlay creation
                cow_create_call = None
                for call_args in mock_subprocess.call_args_list:
                    if 'qemu-img' in call_args[0][0] and 'create' in call_args[0][0] and '-b' in call_args[0][0]:
                        cow_create_call = call_args[0][0]
                        break
                
                assert cow_create_call is not None, "COW overlay creation should be called"
                assert '-b' in cow_create_call  # Backing file option
                assert '-F' in cow_create_call  # Backing format option
    
    def test_base_image_reuse(self, kvm_provider):
        """Test that base image creation is skipped when image already exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            vm_disk_dir = Path(temp_dir)
            base_image_path = vm_disk_dir / "base.qcow2"
            
            # Create existing base image with substantial size (>1024 bytes as per code logic)
            base_image_path.write_bytes(b"existing base image content" * 100)  # Create ~2.7KB file
            
            mock_guest = MagicMock()
            mock_guest.basevm_config_file = None
            
            with patch.object(kvm_provider, '_ensure_bootable_base_image') as mock_ensure_base, \
                 patch('subprocess.run') as mock_subprocess:
                
                # Mock successful subprocess calls
                mock_subprocess.return_value = MagicMock(returncode=0)
                
                # Mock the base_image_dir to point to our temp directory 
                with patch.object(kvm_provider, 'base_image_dir', vm_disk_dir):
                    vm_disk_path = kvm_provider._create_vm_disk("test-vm", mock_guest)
                
                # Should not have called _ensure_bootable_base_image since file exists
                mock_ensure_base.assert_not_called()
                
                # Should have created COW overlay
                assert mock_subprocess.called
                
                # Verify the created disk path
                assert "test-vm" in vm_disk_path


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    @pytest.fixture
    def kvm_provider(self):
        """Create KVM provider instance for testing"""
        settings = CyRISSettings()
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': str(settings.cyber_range_dir),
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        return KVMProvider(kvm_config)
    
    def test_network_unavailable_during_download(self, kvm_provider):
        """Test behavior when network is unavailable"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_image_path = Path(temp_dir) / "base.qcow2"
            
            with patch('urllib.request.urlretrieve', side_effect=OSError("Network unreachable")), \
                 patch('subprocess.run') as mock_subprocess:
                
                mock_subprocess.return_value = MagicMock(returncode=0)
                
                # Should fall back to empty image
                kvm_provider._ensure_bootable_base_image(base_image_path)
                
                # Verify fallback empty image creation
                mock_subprocess.assert_called_with([
                    "qemu-img", "create", "-f", "qcow2", 
                    str(base_image_path), "10G"
                ], check=True)
    
    def test_insufficient_disk_space(self, kvm_provider):
        """Test behavior with insufficient disk space"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_image_path = Path(temp_dir) / "base.qcow2"
            
            with patch('urllib.request.urlretrieve') as mock_download, \
                 patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "qemu-img")):
                
                # Should handle qemu-img failures gracefully
                with pytest.raises((subprocess.CalledProcessError, Exception)):
                    kvm_provider._ensure_bootable_base_image(base_image_path)
    
    def test_permission_errors_cloud_init(self, kvm_provider):
        """Test handling of permission errors during cloud-init creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            disk_dir = Path(temp_dir)
            
            with patch('pathlib.Path.mkdir', side_effect=PermissionError("Access denied")):
                # Should handle permission errors gracefully
                with pytest.raises(PermissionError):
                    kvm_provider._create_cloud_init_config(disk_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])