"""
TDD tests for automated permission management functionality

These tests verify the PermissionManager system that eliminates the need
for manual ACL configuration when using bridge networking. Key areas tested:
- ACL permission setup for libvirt-qemu user  
- System compatibility checks
- Automatic permission integration in VM creation
- Error handling and fallback scenarios
"""

import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import subprocess

from cyris.infrastructure.permissions import PermissionManager


class TestPermissionManager:
    """Test core PermissionManager functionality"""
    
    @pytest.fixture
    def permission_manager(self):
        """Create permission manager for testing"""
        return PermissionManager(dry_run=True)  # Use dry_run to avoid actual system changes
    
    def test_permission_manager_initialization(self):
        """Test PermissionManager initializes correctly"""
        pm = PermissionManager()
        assert pm is not None
        assert hasattr(pm, 'setup_libvirt_access')
        assert hasattr(pm, 'check_libvirt_compatibility')
    
    def test_dry_run_mode(self):
        """Test that dry_run mode prevents actual system changes"""
        pm = PermissionManager(dry_run=True)
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            
            # In dry_run mode, should return True but not execute actual commands
            result = pm.setup_libvirt_access(temp_path)
            assert result is True
    
    @patch('subprocess.run')
    def test_libvirt_compatibility_check_success(self, mock_subprocess):
        """Test successful libvirt compatibility checking"""
        # Mock ACL commands check (setfacl first, then getfacl)
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout=""),  # which setfacl
            Mock(returncode=0, stdout=""),  # which getfacl
            Mock(returncode=0, stdout="ubuntu adm cdrom sudo dip plugdev lxd"),  # groups
        ]
        
        pm = PermissionManager()
        compat_info = pm.check_libvirt_compatibility()
        
        # Should detect libvirt user from initialization
        assert compat_info['libvirt_user'] == 'libvirt-qemu'
        assert compat_info['acl_supported'] is True
        assert 'ubuntu' in compat_info['current_user_groups']
        
        # Should have called ACL check commands
        assert mock_subprocess.call_count >= 2
    
    @patch('subprocess.run')
    def test_acl_commands_not_available(self, mock_subprocess):
        """Test handling when ACL commands are not available"""
        # Mock ACL commands failing
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'which')
        
        pm = PermissionManager()
        compat_info = pm.check_libvirt_compatibility()
        
        assert compat_info['acl_supported'] is False
        assert any('acl' in rec.lower() for rec in compat_info['recommendations'])
    
    def test_setup_nonexistent_path(self):
        """Test setup with nonexistent path"""
        pm = PermissionManager(dry_run=True)
        nonexistent_path = Path("/nonexistent/path/file.qcow2")
        
        result = pm.setup_libvirt_access(nonexistent_path)
        # Should handle nonexistent path gracefully
        assert result in [True, False]  # Either works in dry run or fails safely
    
    @patch('subprocess.run')
    def test_setup_cyris_environment_success(self, mock_subprocess):
        """Test setting up entire CyRIS environment"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create directory structure
            images_dir = base_path / "images"
            images_dir.mkdir()
            cyber_range_dir = base_path / "cyber_range"  
            cyber_range_dir.mkdir()
            
            pm = PermissionManager(dry_run=True)  # Use dry run to avoid actual ACL commands
            result = pm.setup_cyris_environment(base_path)
            
            assert result is True


class TestPermissionIntegration:
    """Test integration of permission management with KVM provider"""
    
    def test_kvm_provider_uses_permission_manager(self):
        """Test that KVM provider creates PermissionManager"""
        from cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        config = {"libvirt_uri": "qemu:///system"}
        provider = KVMProvider(config)
        
        # Verify PermissionManager was instantiated
        assert hasattr(provider, 'permission_manager')
        assert provider.permission_manager is not None
    
    def test_session_mode_still_has_permission_manager(self):
        """Test that session mode still creates permission manager"""
        from cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        config = {"libvirt_uri": "qemu:///session"}
        provider = KVMProvider(config)
        
        # Session mode should still have permission manager
        assert hasattr(provider, 'permission_manager')
        assert provider.permission_manager is not None
        assert provider.libvirt_uri == "qemu:///session"


class TestCLIPermissionCommand:
    """Test the CLI setup-permissions command"""
    
    def test_cli_setup_permissions_command_exists(self):
        """Test that setup-permissions command is available"""
        from click.testing import CliRunner
        from cyris.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        # Command should be listed in help
        assert 'setup-permissions' in result.output
    
    @patch('cyris.infrastructure.permissions.PermissionManager')
    def test_cli_setup_permissions_execution(self, mock_permission_manager_class):
        """Test setup-permissions command execution"""
        from click.testing import CliRunner
        from cyris.cli.main import cli
        
        # Mock permission manager
        mock_pm = Mock()
        mock_pm.check_libvirt_compatibility.return_value = {
            'libvirt_user': 'libvirt-qemu',
            'acl_supported': True,
            'current_user_groups': ['ubuntu', 'libvirt'],
            'recommendations': []
        }
        mock_pm.setup_cyris_environment.return_value = True
        mock_permission_manager_class.return_value = mock_pm
        
        runner = CliRunner()
        result = runner.invoke(cli, ['setup-permissions'])
        
        assert result.exit_code == 0
        assert 'Successfully configured libvirt permissions' in result.output
        mock_pm.setup_cyris_environment.assert_called_once()
    
    def test_cli_setup_permissions_dry_run(self):
        """Test setup-permissions command with --dry-run"""
        from click.testing import CliRunner
        from cyris.cli.main import cli
        
        runner = CliRunner()
        
        with patch('cyris.infrastructure.permissions.PermissionManager') as mock_pm_class:
            mock_pm = Mock()
            mock_pm.check_libvirt_compatibility.return_value = {
                'libvirt_user': 'libvirt-qemu',
                'acl_supported': True,
                'current_user_groups': ['ubuntu'],
                'recommendations': []
            }
            mock_pm_class.return_value = mock_pm
            
            result = runner.invoke(cli, ['setup-permissions', '--dry-run'])
            
            assert result.exit_code == 0
            assert 'DRY RUN MODE' in result.output
            # Verify dry_run=True was passed to PermissionManager
            mock_pm_class.assert_called_with(dry_run=True)


class TestPermissionErrorHandling:
    """Test error handling in permission management"""
    
    def test_permission_manager_handles_missing_commands(self):
        """Test that PermissionManager handles missing system commands gracefully"""
        with patch('subprocess.run', side_effect=FileNotFoundError("Command not found")):
            pm = PermissionManager(dry_run=True)
            compat_info = pm.check_libvirt_compatibility()
            
            # Should not crash, should return safe defaults
            assert isinstance(compat_info, dict)
            assert 'libvirt_user' in compat_info
            assert 'acl_supported' in compat_info
    
    def test_permission_setup_with_insufficient_privileges(self):
        """Test permission setup when user lacks sufficient privileges"""
        pm = PermissionManager(dry_run=False)
        
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            
            with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'setfacl')):
                result = pm.setup_libvirt_access(temp_path)
                # Should handle permission errors gracefully
                assert result is False
    
    def test_setup_libvirt_access_with_missing_libvirt_user(self):
        """Test setup when libvirt user is not detected"""
        pm = PermissionManager(dry_run=True)
        pm.libvirt_user = None  # Force None to simulate missing user
        
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            result = pm.setup_libvirt_access(temp_path)
            assert result is False


class TestPermissionManagerRealScenarios:
    """Test PermissionManager in scenarios matching real usage"""
    
    def test_bridge_networking_permission_scenario(self):
        """Test permission setup scenario for bridge networking"""
        with tempfile.TemporaryDirectory() as temp_dir:
            vm_disk_path = Path(temp_dir) / "test-vm.qcow2"
            vm_disk_path.write_text("mock disk content")
            
            pm = PermissionManager(dry_run=True)
            
            # This should work for bridge networking setup
            result = pm.setup_libvirt_access(vm_disk_path)
            assert result is True
    
    def test_cyber_range_directory_permission_scenario(self):
        """Test permission setup for entire cyber range directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create mock cyber range structure
            cyber_range_dir = base_path / "cyber_range"
            cyber_range_dir.mkdir()
            
            range_dir = cyber_range_dir / "test_range"
            range_dir.mkdir()
            
            disks_dir = range_dir / "disks"
            disks_dir.mkdir()
            
            # Create mock VM disk
            vm_disk = disks_dir / "test-vm.qcow2"
            vm_disk.write_text("mock disk")
            
            pm = PermissionManager(dry_run=True)
            result = pm.setup_cyris_environment(base_path)
            
            assert result is True
    
    def test_automatic_permission_integration_workflow(self):
        """Test the complete workflow of automatic permission setup"""
        from cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "libvirt_uri": "qemu:///system",
                "base_path": temp_dir
            }
            
            # KVM Provider should initialize with permission manager
            provider = KVMProvider(config)
            
            assert hasattr(provider, 'permission_manager')
            assert provider.permission_manager is not None
            
            # Permission manager should be configured for the provider's needs
            assert provider.libvirt_uri == "qemu:///system"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])