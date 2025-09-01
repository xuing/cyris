"""
End-to-end tests for complete CyRIS workflow validation.
Tests the entire pipeline from YAML configuration to VM deployment and task execution.
"""

import pytest
import tempfile
import subprocess
import time
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.cyris.services.orchestrator import RangeOrchestrator
from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
from src.cyris.config.settings import CyRISSettings
from src.cyris.cli.main import cli
from click.testing import CliRunner


class TestCompleteWorkflowE2E:
    """End-to-end tests for complete CyRIS workflow validation"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for E2E testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            # Create subdirectories
            (workspace / "configs").mkdir()
            (workspace / "cyber_range").mkdir()
            yield workspace
    
    @pytest.fixture
    def sample_yaml_config(self, temp_workspace):
        """Create sample YAML configuration for testing"""
        config = {
            "host_settings": [
                {
                    "id": "test-host-1",
                    "virbr_addr": "192.168.122.1",
                    "mgmt_addr": "10.0.1.100",
                    "account": "ubuntu"
                }
            ],
            "guest_settings": [
                {
                    "id": "desktop",
                    "ip_addr": "192.168.1.100",
                    "root_passwd": "ubuntu",
                    "basevm_host": "test-host-1",
                    "basevm_config_file": "",
                    "basevm_os_type": "ubuntu",
                    "basevm_type": "kvm",
                    "basevm_name": "ubuntu-desktop",
                    "tasks": [
                        {
                            "task_type": "add_account",
                            "username": "testuser",
                            "password": "testpass123",
                            "groups": ["users"],
                            "sudo_access": True
                        }
                    ]
                }
            ],
            "clone_settings": [
                {
                    "range_id": 1001,
                    "hosts": [
                        {
                            "host_id": "test-host-1",
                            "instance_number": 1,
                            "guests": [
                                {
                                    "guest_id": "desktop",
                                    "tasks": [
                                        {
                                            "task_type": "install_package",
                                            "package_name": "htop",
                                            "package_manager": "apt"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        config_file = temp_workspace / "configs" / "test_range.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_file
    
    @pytest.fixture
    def settings(self, temp_workspace):
        """Create settings with temporary workspace"""
        settings = CyRISSettings()
        settings.cyber_range_dir = temp_workspace / "cyber_range"
        settings.cyris_path = temp_workspace
        return settings
    
    @pytest.fixture
    def orchestrator(self, settings):
        """Create orchestrator for E2E testing"""
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': str(settings.cyber_range_dir),
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        kvm_provider = KVMProvider(kvm_config)
        return RangeOrchestrator(settings, kvm_provider)
    
    def test_yaml_to_vm_creation_e2e(self, orchestrator, sample_yaml_config):
        """Test complete YAML configuration to VM creation workflow"""
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch.object(orchestrator, '_get_vm_ip_by_name') as mock_get_ip, \
             patch.object(orchestrator.task_executor, 'execute_guest_tasks') as mock_execute_tasks:
            
            # Mock successful VM creation
            mock_create_hosts.return_value = ["test-host-1"]
            mock_create_guests.return_value = ["cyris-desktop-abc123"]
            mock_get_ip.return_value = "192.168.122.100"
            
            # Mock successful task execution
            from src.cyris.services.task_executor import TaskResult, TaskType
            mock_task_result = TaskResult(
                task_id="test-task-1",
                task_type=TaskType.ADD_ACCOUNT,
                success=True,
                message="User testuser created successfully",
                evidence="User testuser exists with sudo access"
            )
            mock_execute_tasks.return_value = [mock_task_result]
            
            # Create range from YAML
            result = orchestrator.create_range_from_yaml(sample_yaml_config)
            
            # Verify range creation
            assert result is not None
            range_metadata = orchestrator.get_range(result)
            assert range_metadata is not None
            assert range_metadata.status.value == "active"
            
            # Verify tasks were executed
            mock_execute_tasks.assert_called_once()
    
    def test_cli_create_command_e2e(self, sample_yaml_config, settings):
        """Test CLI create command end-to-end workflow"""
        runner = CliRunner()
        
        with patch('src.cyris.services.orchestrator.RangeOrchestrator') as MockOrchestrator:
            # Mock orchestrator behavior
            mock_orchestrator_instance = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.range_id = "1001"
            mock_metadata.name = "Test Range"
            mock_metadata.status.value = "active"
            
            mock_orchestrator_instance.create_range_from_yaml.return_value = mock_metadata.range_id
            mock_orchestrator_instance.get_range.return_value = mock_metadata
            MockOrchestrator.return_value = mock_orchestrator_instance
            
            # Run CLI create command
            result = runner.invoke(cli, ['create', str(sample_yaml_config)])
            
            # Verify command execution
            assert result.exit_code == 0
            assert "successfully created" in result.output.lower()
            mock_orchestrator_instance.create_range_from_yaml.assert_called_once()
    
    def test_cli_status_command_e2e(self, sample_yaml_config, settings):
        """Test CLI status command end-to-end workflow"""
        runner = CliRunner()
        
        with patch('src.cyris.services.orchestrator.RangeOrchestrator') as MockOrchestrator:
            # Mock orchestrator with detailed status
            mock_orchestrator_instance = MagicMock()
            mock_detailed_status = {
                "range_id": "1001",
                "name": "Test Range",
                "description": "E2E test range",
                "status": "active",
                "created_at": "2025-09-01T12:00:00",
                "last_modified": "2025-09-01T12:00:00",
                "vm_count": 1,
                "vms": [
                    {
                        "name": "cyris-desktop-abc123",
                        "ip": "192.168.122.100",
                        "status": "running",
                        "ssh_accessible": True,
                        "error_details": None,
                        "last_checked": "2025-09-01T12:30:00"
                    }
                ],
                "topology_metadata": None,
                "provider": "kvm"
            }
            
            mock_orchestrator_instance.get_range_status_detailed.return_value = mock_detailed_status
            MockOrchestrator.return_value = mock_orchestrator_instance
            
            # Run CLI status command
            result = runner.invoke(cli, ['status', '1001', '--verbose'])
            
            # Verify command execution and output
            assert result.exit_code == 0
            assert "Test Range" in result.output
            assert "cyris-desktop-abc123" in result.output
            assert "192.168.122.100" in result.output
            assert "Running" in result.output
    
    def test_cli_list_command_e2e(self, settings):
        """Test CLI list command end-to-end workflow"""
        runner = CliRunner()
        
        with patch('src.cyris.services.orchestrator.RangeOrchestrator') as MockOrchestrator:
            # Mock orchestrator with range list
            mock_orchestrator_instance = MagicMock()
            mock_ranges = [
                MagicMock(
                    range_id="1001",
                    name="Test Range 1",
                    status=MagicMock(value="active"),
                    created_at=MagicMock(strftime=lambda fmt: "2025-09-01 12:00:00")
                ),
                MagicMock(
                    range_id="1002", 
                    name="Test Range 2",
                    status=MagicMock(value="creating"),
                    created_at=MagicMock(strftime=lambda fmt: "2025-09-01 12:15:00")
                )
            ]
            
            mock_orchestrator_instance.list_ranges.return_value = mock_ranges
            MockOrchestrator.return_value = mock_orchestrator_instance
            
            # Run CLI list command
            result = runner.invoke(cli, ['list', '--all', '--verbose'])
            
            # Verify command execution and output
            assert result.exit_code == 0
            assert "1001" in result.output
            assert "1002" in result.output
            assert "Test Range 1" in result.output
            assert "Test Range 2" in result.output
    
    def test_range_lifecycle_complete_e2e(self, orchestrator, sample_yaml_config):
        """Test complete range lifecycle: create → status → destroy"""
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch.object(orchestrator.provider, 'destroy_hosts') as mock_destroy_hosts, \
             patch.object(orchestrator.provider, 'destroy_guests') as mock_destroy_guests, \
             patch.object(orchestrator, '_get_vm_ip_by_name') as mock_get_ip:
            
            # Mock successful creation
            mock_create_hosts.return_value = ["test-host-1"]
            mock_create_guests.return_value = ["cyris-desktop-abc123"]
            mock_get_ip.return_value = "192.168.122.100"
            
            # 1. Create range
            range_id = orchestrator.create_range_from_yaml(sample_yaml_config)
            assert range_id is not None
            
            # 2. Check status
            metadata = orchestrator.get_range(range_id)
            assert metadata is not None
            assert metadata.status.value == "active"
            
            detailed_status = orchestrator.get_range_status_detailed(range_id)
            assert detailed_status is not None
            assert detailed_status["range_id"] == range_id
            
            # 3. Destroy range
            destroyed = orchestrator.destroy_range(range_id)
            assert destroyed is True
            
            # 4. Verify cleanup
            mock_destroy_guests.assert_called_once()
            mock_destroy_hosts.assert_called_once()
    
    def test_error_handling_e2e(self, orchestrator, sample_yaml_config):
        """Test error handling throughout the E2E workflow"""
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests:
            
            # Mock host creation success, guest creation failure
            mock_create_hosts.return_value = ["test-host-1"]
            mock_create_guests.side_effect = Exception("VM creation failed")
            
            # Attempt range creation - should fail gracefully
            with pytest.raises(Exception) as exc_info:
                orchestrator.create_range_from_yaml(sample_yaml_config)
            
            assert "VM creation failed" in str(exc_info.value)
    
    def test_task_execution_verification_e2e(self, orchestrator, sample_yaml_config):
        """Test task execution and verification end-to-end"""
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch.object(orchestrator, '_get_vm_ip_by_name') as mock_get_ip, \
             patch.object(orchestrator.task_executor, 'execute_guest_tasks') as mock_execute_tasks:
            
            # Mock successful VM creation
            mock_create_hosts.return_value = ["test-host-1"]
            mock_create_guests.return_value = ["cyris-desktop-abc123"]
            mock_get_ip.return_value = "192.168.122.100"
            
            # Mock task execution with both success and failure
            from src.cyris.services.task_executor import TaskResult, TaskType
            mock_task_results = [
                TaskResult(
                    task_id="add-user",
                    task_type=TaskType.ADD_ACCOUNT,
                    success=True,
                    message="User testuser created successfully",
                    evidence="User testuser exists in /etc/passwd"
                ),
                TaskResult(
                    task_id="install-package",
                    task_type=TaskType.INSTALL_PACKAGE,
                    success=True,
                    message="Package htop installed successfully",
                    evidence="htop package installed and available"
                )
            ]
            mock_execute_tasks.return_value = mock_task_results
            
            # Create range with tasks
            range_id = orchestrator.create_range_from_yaml(sample_yaml_config)
            
            # Verify tasks were executed
            mock_execute_tasks.assert_called_once()
            
            # Verify task results are stored in metadata
            metadata = orchestrator.get_range(range_id)
            assert 'task_results' in metadata.tags
    
    def test_ip_discovery_integration_e2e(self, orchestrator, sample_yaml_config):
        """Test IP discovery integration throughout E2E workflow"""
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch('src.cyris.tools.vm_ip_manager.get_vm_ip_simple') as mock_get_ip_simple:
            
            # Mock successful VM creation
            mock_create_hosts.return_value = ["test-host-1"] 
            mock_create_guests.return_value = ["cyris-desktop-abc123"]
            
            # Mock IP discovery with different scenarios
            def ip_discovery_side_effect(vm_name):
                if vm_name == "cyris-desktop-abc123":
                    return "192.168.122.100", None
                else:
                    return None, "VM not found in DHCP leases; Network Interface: present"
            
            mock_get_ip_simple.side_effect = ip_discovery_side_effect
            
            # Create range
            range_id = orchestrator.create_range_from_yaml(sample_yaml_config)
            
            # Get detailed status to verify IP discovery
            status = orchestrator.get_range_status_detailed(range_id)
            
            # Verify IP was discovered and stored
            assert status is not None
            assert len(status["vms"]) == 1
            vm_info = status["vms"][0]
            assert vm_info["name"] == "cyris-desktop-abc123"
            assert vm_info["ip"] == "192.168.122.100"
            assert vm_info["error_details"] is None
    
    def test_legacy_compatibility_e2e(self, temp_workspace, sample_yaml_config):
        """Test legacy command compatibility end-to-end"""
        runner = CliRunner()
        
        with patch('subprocess.run') as mock_subprocess:
            # Mock successful legacy execution
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Legacy range created successfully"
            mock_subprocess.return_value = mock_result
            
            # Run legacy command through CLI
            result = runner.invoke(cli, ['legacy', str(sample_yaml_config), str(temp_workspace / "CONFIG")])
            
            # Verify legacy execution
            assert result.exit_code == 0
            mock_subprocess.assert_called_once()
    
    def test_configuration_validation_e2e(self, temp_workspace):
        """Test configuration validation end-to-end"""
        # Create invalid YAML config
        invalid_config = {
            "host_settings": [
                {
                    "id": "test-host",
                    # Missing required fields
                }
            ]
        }
        
        invalid_config_file = temp_workspace / "configs" / "invalid.yml"
        with open(invalid_config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        runner = CliRunner()
        
        # Run create command with invalid config
        result = runner.invoke(cli, ['create', str(invalid_config_file)])
        
        # Should fail gracefully with error message
        assert result.exit_code != 0
        assert "error" in result.output.lower() or "failed" in result.output.lower()
    
    def test_cleanup_and_resource_management_e2e(self, orchestrator, sample_yaml_config):
        """Test cleanup and resource management end-to-end"""
        
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts, \
             patch.object(orchestrator.provider, 'create_guests') as mock_create_guests, \
             patch.object(orchestrator, '_cleanup_range_resources') as mock_cleanup:
            
            # Mock successful VM creation
            mock_create_hosts.return_value = ["test-host-1"]
            mock_create_guests.return_value = ["cyris-desktop-abc123"]
            
            # Create and destroy range
            range_id = orchestrator.create_range_from_yaml(sample_yaml_config)
            success = orchestrator.destroy_range(range_id)
            
            # Verify cleanup was called
            assert success is True
            mock_cleanup.assert_called_once_with(range_id)
            
            # Verify range metadata is updated
            metadata = orchestrator.get_range(range_id)
            assert metadata.status.value == "destroyed"


class TestCLIWorkflowE2E:
    """End-to-end tests for CLI workflow scenarios"""
    
    def test_full_cli_workflow_scenario(self, temp_workspace):
        """Test a complete CLI workflow scenario"""
        runner = CliRunner()
        
        # Create sample config
        config_file = temp_workspace / "test_cli_workflow.yml"
        sample_config = {
            "host_settings": [{"id": "host1", "mgmt_addr": "10.0.1.100", "account": "ubuntu"}],
            "guest_settings": [{"id": "vm1", "basevm_host": "host1"}],
            "clone_settings": [{"range_id": 2001}]
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        with patch('src.cyris.services.orchestrator.RangeOrchestrator') as MockOrchestrator:
            # Mock orchestrator for the full workflow
            mock_orchestrator_instance = MagicMock()
            
            # Mock create operation
            mock_orchestrator_instance.create_range_from_yaml.return_value = "2001"
            
            # Mock get_range for immediate status check
            mock_metadata = MagicMock()
            mock_metadata.range_id = "2001"
            mock_metadata.name = "Range 2001"
            mock_metadata.status.value = "active"
            mock_orchestrator_instance.get_range.return_value = mock_metadata
            
            # Mock list operation
            mock_orchestrator_instance.list_ranges.return_value = [mock_metadata]
            
            # Mock detailed status
            mock_detailed_status = {
                "range_id": "2001",
                "name": "Range 2001",
                "status": "active",
                "vm_count": 1,
                "vms": [{"name": "vm1", "ip": "192.168.122.100", "status": "running"}]
            }
            mock_orchestrator_instance.get_range_status_detailed.return_value = mock_detailed_status
            
            # Mock destroy operation
            mock_orchestrator_instance.destroy_range.return_value = True
            
            MockOrchestrator.return_value = mock_orchestrator_instance
            
            # 1. Create range
            result1 = runner.invoke(cli, ['create', str(config_file)])
            assert result1.exit_code == 0
            assert "successfully created" in result1.output.lower()
            
            # 2. List ranges
            result2 = runner.invoke(cli, ['list'])
            assert result2.exit_code == 0
            assert "2001" in result2.output
            
            # 3. Check status
            result3 = runner.invoke(cli, ['status', '2001'])
            assert result3.exit_code == 0
            assert "Range 2001" in result3.output
            
            # 4. Destroy range
            result4 = runner.invoke(cli, ['destroy', '2001'])
            assert result4.exit_code == 0
            assert "destroyed" in result4.output.lower()
            
            # Verify all operations were called
            mock_orchestrator_instance.create_range_from_yaml.assert_called_once()
            mock_orchestrator_instance.list_ranges.assert_called()
            mock_orchestrator_instance.get_range_status_detailed.assert_called()
            mock_orchestrator_instance.destroy_range.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])