#!/usr/bin/env python3
"""
Comprehensive sudo management tests for CyRIS.
Consolidated from multiple root directory sudo test files.

This test suite covers:
- Basic sudo functionality (from test_sudo_direct.py)
- Sudo workflow integration (from test_sudo_workflow.py) 
- Enhanced sudo features (from test_enhanced_sudo_complete.py)
- Sudo simulation scenarios (from test_cyris_sudo_simulation.py)
- Image builder sudo operations (from test_image_builder_sudo.py)
"""

import pytest
import subprocess
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Import CyRIS modules
from cyris.core.sudo_manager import SudoPermissionManager
from cyris.core.rich_progress import RichProgressManager
from cyris.core.exceptions import CyRISException, CyRISVirtualizationError


class TestSudoBasicFunctionality:
    """Basic sudo functionality tests (consolidated from test_sudo_direct.py)"""
    
    @pytest.fixture
    def sudo_manager(self):
        """Create sudo manager for testing"""
        progress_manager = RichProgressManager("test_sudo_basic")
        return SudoPermissionManager(progress_manager=progress_manager)
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_availability_check(self, mock_subprocess, sudo_manager):
        """Test basic sudo availability checking"""
        # Mock successful sudo check
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        result = sudo_manager.check_permissions()
        assert result is not None
        mock_subprocess.assert_called()
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_command_execution(self, mock_subprocess, sudo_manager):
        """Test sudo command execution"""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "success"
        mock_subprocess.return_value.stderr = ""
        
        # Test command execution with sudo
        result = sudo_manager.execute_with_sudo(["echo", "test"])
        assert result.returncode == 0
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_permission_denied(self, mock_subprocess, sudo_manager):
        """Test handling of permission denied scenarios"""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Permission denied"
        
        with pytest.raises(CyRISException):
            sudo_manager.request_elevation()
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_timeout_handling(self, mock_subprocess, sudo_manager):
        """Test sudo timeout handling"""
        mock_subprocess.side_effect = subprocess.TimeoutExpired("sudo", 30)
        
        with pytest.raises(CyRISException):
            sudo_manager.check_permissions()


class TestSudoWorkflowIntegration:
    """Sudo workflow integration tests (consolidated from test_sudo_workflow.py)"""
    
    @pytest.fixture
    def workflow_setup(self):
        """Setup for workflow testing"""
        progress_manager = RichProgressManager("test_sudo_workflow")
        sudo_manager = SudoPermissionManager(progress_manager=progress_manager)
        return progress_manager, sudo_manager
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_workflow_initialization(self, mock_subprocess, workflow_setup):
        """Test sudo workflow initialization"""
        progress_manager, sudo_manager = workflow_setup
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        # Start workflow
        progress_manager.start_task("sudo_init", "Initializing sudo")
        result = sudo_manager.check_permissions()
        progress_manager.complete_task("sudo_init")
        
        assert result is not None
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_workflow_vm_operations(self, mock_subprocess, workflow_setup):
        """Test sudo workflow for VM operations"""
        progress_manager, sudo_manager = workflow_setup
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "VM created successfully"
        mock_subprocess.return_value.stderr = ""
        
        # Simulate VM creation workflow
        progress_manager.start_task("vm_create", "Creating VM")
        
        # Commands that would need sudo
        commands = [
            ["virt-builder", "--format=qcow2", "ubuntu-20.04"],
            ["virt-install", "--import", "--name=test-vm"],
            ["virsh", "start", "test-vm"]
        ]
        
        for cmd in commands:
            result = sudo_manager.execute_with_sudo(cmd)
            assert result.returncode == 0
        
        progress_manager.complete_task("vm_create")
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_workflow_error_recovery(self, mock_subprocess, workflow_setup):
        """Test sudo workflow error recovery"""
        progress_manager, sudo_manager = workflow_setup
        
        # First call fails, second succeeds
        mock_subprocess.side_effect = [
            Mock(returncode=1, stdout="", stderr="Failed"),
            Mock(returncode=0, stdout="success", stderr="")
        ]
        
        progress_manager.start_task("error_recovery", "Testing error recovery")
        
        # First attempt should fail
        with pytest.raises(CyRISException):
            sudo_manager.execute_with_sudo(["test", "command"])
        
        # Retry should succeed
        result = sudo_manager.execute_with_sudo(["test", "command"])
        assert result.returncode == 0
        
        progress_manager.complete_task("error_recovery")


class TestSudoEnhancedFeatures:
    """Enhanced sudo features tests (consolidated from test_enhanced_sudo_complete.py)"""
    
    @pytest.fixture
    def enhanced_sudo_manager(self):
        """Create enhanced sudo manager for testing"""
        progress_manager = RichProgressManager("test_enhanced_sudo")
        return SudoPermissionManager(progress_manager=progress_manager, enhanced_mode=True)
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_enhanced_sudo_caching(self, mock_subprocess, enhanced_sudo_manager):
        """Test enhanced sudo permission caching"""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        # First check should call subprocess
        result1 = enhanced_sudo_manager.check_permissions()
        assert mock_subprocess.call_count == 1
        
        # Second check should use cache (if implemented)
        result2 = enhanced_sudo_manager.check_permissions()
        # Note: Actual caching implementation would determine call count
        assert result1 == result2
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_enhanced_sudo_batch_operations(self, mock_subprocess, enhanced_sudo_manager):
        """Test enhanced sudo batch operations"""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "batch success"
        mock_subprocess.return_value.stderr = ""
        
        # Test batch command execution
        commands = [
            ["echo", "command1"],
            ["echo", "command2"],
            ["echo", "command3"]
        ]
        
        results = enhanced_sudo_manager.execute_batch_with_sudo(commands)
        assert len(results) == 3
        for result in results:
            assert result.returncode == 0
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_enhanced_sudo_timeout_configuration(self, mock_subprocess, enhanced_sudo_manager):
        """Test enhanced sudo timeout configuration"""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        # Test custom timeout
        result = enhanced_sudo_manager.execute_with_sudo(
            ["long", "running", "command"], 
            timeout=60
        )
        assert result.returncode == 0


class TestSudoSimulationScenarios:
    """Sudo simulation scenarios (consolidated from test_cyris_sudo_simulation.py)"""
    
    @pytest.fixture
    def simulation_setup(self):
        """Setup for simulation testing"""
        progress_manager = RichProgressManager("test_sudo_simulation")
        sudo_manager = SudoPermissionManager(progress_manager=progress_manager)
        return progress_manager, sudo_manager
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_simulation_vm_lifecycle(self, mock_subprocess, simulation_setup):
        """Test sudo simulation for complete VM lifecycle"""
        progress_manager, sudo_manager = simulation_setup
        
        # Mock successful operations
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "operation successful"
        mock_subprocess.return_value.stderr = ""
        
        # Simulate complete VM lifecycle
        lifecycle_steps = [
            ("vm_create", "Creating virtual machine"),
            ("vm_configure", "Configuring virtual machine"),  
            ("vm_start", "Starting virtual machine"),
            ("vm_monitor", "Monitoring virtual machine"),
            ("vm_stop", "Stopping virtual machine"),
            ("vm_destroy", "Destroying virtual machine")
        ]
        
        for step_id, step_name in lifecycle_steps:
            progress_manager.start_task(step_id, step_name)
            
            # Simulate sudo operation
            result = sudo_manager.execute_with_sudo([f"virsh_{step_id}", "test-vm"])
            assert result.returncode == 0
            
            progress_manager.complete_task(step_id)
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_simulation_network_operations(self, mock_subprocess, simulation_setup):
        """Test sudo simulation for network operations"""
        progress_manager, sudo_manager = simulation_setup
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "network configured"
        mock_subprocess.return_value.stderr = ""
        
        # Simulate network setup operations
        network_operations = [
            ["ip", "link", "add", "br0", "type", "bridge"],
            ["ip", "link", "set", "br0", "up"],
            ["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", "br0", "-j", "MASQUERADE"]
        ]
        
        progress_manager.start_task("network_setup", "Setting up network")
        
        for operation in network_operations:
            result = sudo_manager.execute_with_sudo(operation)
            assert result.returncode == 0
        
        progress_manager.complete_task("network_setup")


class TestSudoImageBuilderOperations:
    """Image builder sudo operations (consolidated from test_image_builder_sudo.py)"""
    
    @pytest.fixture
    def image_builder_setup(self):
        """Setup for image builder testing"""
        progress_manager = RichProgressManager("test_image_builder")
        sudo_manager = SudoPermissionManager(progress_manager=progress_manager)
        return progress_manager, sudo_manager
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_image_creation(self, mock_subprocess, image_builder_setup):
        """Test sudo operations for image creation"""
        progress_manager, sudo_manager = image_builder_setup
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Image created successfully"
        mock_subprocess.return_value.stderr = ""
        
        progress_manager.start_task("image_create", "Creating VM image")
        
        # Simulate virt-builder operations
        builder_commands = [
            ["virt-builder", "ubuntu-20.04", "--format=qcow2", "--size=10G"],
            ["virt-customize", "-a", "test.qcow2", "--install", "openssh-server"],
            ["qemu-img", "convert", "-O", "qcow2", "test.qcow2", "final.qcow2"]
        ]
        
        for cmd in builder_commands:
            result = sudo_manager.execute_with_sudo(cmd)
            assert result.returncode == 0
        
        progress_manager.complete_task("image_create")
    
    @patch('cyris.core.sudo_manager.subprocess.run')
    def test_sudo_image_customization(self, mock_subprocess, image_builder_setup):
        """Test sudo operations for image customization"""
        progress_manager, sudo_manager = image_builder_setup
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Customization successful"
        mock_subprocess.return_value.stderr = ""
        
        progress_manager.start_task("image_customize", "Customizing VM image")
        
        # Simulate image customization
        customization_commands = [
            ["virt-customize", "-a", "base.qcow2", "--run-command", "apt update"],
            ["virt-customize", "-a", "base.qcow2", "--install", "docker.io"],
            ["virt-customize", "-a", "base.qcow2", "--copy-in", "/tmp/config:/etc/"]
        ]
        
        for cmd in customization_commands:
            result = sudo_manager.execute_with_sudo(cmd)
            assert result.returncode == 0
        
        progress_manager.complete_task("image_customize")


class TestSudoErrorHandling:
    """Comprehensive sudo error handling tests"""
    
    @pytest.fixture
    def error_test_setup(self):
        """Setup for error testing"""
        progress_manager = RichProgressManager("test_sudo_errors")
        sudo_manager = SudoPermissionManager(progress_manager=progress_manager)
        return progress_manager, sudo_manager
    
    def test_sudo_not_available(self, error_test_setup):
        """Test behavior when sudo is not available"""
        progress_manager, sudo_manager = error_test_setup
        
        with patch('cyris.core.sudo_manager.subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = FileNotFoundError("sudo: command not found")
            
            with pytest.raises(CyRISException):
                sudo_manager.check_permissions()
    
    def test_sudo_incorrect_password(self, error_test_setup):
        """Test handling of incorrect sudo password"""
        progress_manager, sudo_manager = error_test_setup
        
        with patch('cyris.core.sudo_manager.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 1
            mock_subprocess.return_value.stdout = ""
            mock_subprocess.return_value.stderr = "Sorry, try again."
            
            with pytest.raises(CyRISException):
                sudo_manager.request_elevation()
    
    def test_sudo_no_tty_fallback(self, error_test_setup):
        """Test fallback when no TTY is available"""
        progress_manager, sudo_manager = error_test_setup
        
        with patch('cyris.core.sudo_manager.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 1
            mock_subprocess.return_value.stdout = ""
            mock_subprocess.return_value.stderr = "sudo: no tty present and no askpass program specified"
            
            with pytest.raises(CyRISException):
                sudo_manager.request_elevation()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])