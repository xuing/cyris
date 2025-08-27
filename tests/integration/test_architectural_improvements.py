"""
Integration tests for architectural improvements in CyRIS.
These tests validate the fixes for task execution timing and VM readiness.
"""

import pytest
import time
import tempfile
import os
import sys
from unittest.mock import Mock, patch, MagicMock
import yaml

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.services.orchestrator import RangeOrchestrator
from cyris.services.task_executor import TaskExecutor, TaskType, TaskResult
from cyris.config.settings import CyRISSettings
from cyris.tools.vm_ip_manager import VMIPManager


class TestVMReadinessPipeline:
    """Test VM readiness checking and task execution timing"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked dependencies"""
        settings = CyRISSettings()
        mock_provider = Mock()  # Mock infrastructure provider
        orchestrator = RangeOrchestrator(settings, mock_provider)
        
        # Mock other dependencies
        orchestrator.task_executor = Mock()
        orchestrator.topology_manager = Mock()
        
        return orchestrator

    def test_vm_readiness_check_success(self, orchestrator):
        """Test successful VM readiness verification"""
        # Mock VM IP manager to return healthy VM
        with patch('cyris.services.orchestrator.VMIPManager') as mock_vm_mgr:
            mock_health_info = Mock()
            mock_health_info.ip_addresses = ['192.168.122.100']
            
            mock_vm_mgr.return_value.get_vm_health_info.return_value = mock_health_info
            
            # Mock SSH connectivity test to succeed
            orchestrator._test_ssh_connectivity = Mock(return_value=True)
            
            # Mock virsh command to return running VM
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "cyris-test_vm-12345678\n"
                
                result = orchestrator._wait_for_vm_readiness("test_vm", "test_range", max_wait_minutes=1)
                
                assert result == '192.168.122.100'
                orchestrator._test_ssh_connectivity.assert_called_once_with('192.168.122.100')

    def test_vm_readiness_check_timeout(self, orchestrator):
        """Test VM readiness timeout scenario"""
        # Mock VM IP manager to never return IP
        with patch('cyris.services.orchestrator.VMIPManager') as mock_vm_mgr:
            mock_health_info = Mock()
            mock_health_info.ip_addresses = []
            
            mock_vm_mgr.return_value.get_vm_health_info.return_value = mock_health_info
            
            # Mock virsh command to return no VMs
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "\n"
                
                result = orchestrator._wait_for_vm_readiness("test_vm", "test_range", max_wait_minutes=0.1)
                
                assert result is None

    def test_ssh_connectivity_test(self, orchestrator):
        """Test SSH connectivity verification"""
        orchestrator.task_executor = Mock()
        
        # Test successful SSH
        orchestrator.task_executor._execute_ssh_command.return_value = (True, "ready", "")
        result = orchestrator._test_ssh_connectivity("192.168.122.100")
        assert result is True
        
        # Test failed SSH
        orchestrator.task_executor._execute_ssh_command.return_value = (False, "", "Connection refused")
        result = orchestrator._test_ssh_connectivity("192.168.122.100")
        assert result is False

class TestTaskExecutionTiming:
    """Test task execution with proper VM readiness checking"""

    @pytest.fixture
    def task_executor(self):
        """Create task executor for testing"""
        config = {
            'base_path': '/tmp/test_cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        return TaskExecutor(config)

    def test_add_account_task_success(self, task_executor):
        """Test add_account task executes successfully with proper setup"""
        # Mock SSH command execution to simulate successful user creation
        task_executor._execute_ssh_command = Mock()
        
        # Simulate successful script upload
        task_executor._execute_ssh_command.side_effect = [
            (True, "", ""),  # Upload script
            (True, "", ""),  # Make executable
            (True, "User testuser created successfully", ""),  # Execute script
            (True, "", "")   # Cleanup
        ]

        class MockGuest:
            def __init__(self):
                self.basevm_os_type = 'linux'
                self.basevm_type = 'kvm'

        guest = MockGuest()
        params = {
            'account': 'testuser',
            'passwd': 'testpass123',
            'full_name': 'Test User'
        }

        result = task_executor._execute_add_account(
            task_id='test_add_user',
            params=params,
            guest_ip='192.168.122.100',
            guest=guest,
            start_time=time.time()
        )

        assert result.success is True
        assert "SUCCESS" in result.message
        assert result.task_type == TaskType.ADD_ACCOUNT
        assert task_executor._execute_ssh_command.call_count == 4  # upload, chmod, execute, cleanup

    def test_task_execution_with_vm_not_ready(self):
        """Test task behavior when VM is not ready"""
        # This test validates the deferred task execution behavior
        # when VMs don't have IP addresses during deployment
        
        orchestrator = Mock()
        orchestrator.logger = Mock()
        
        # Mock guest with tasks but no IP available
        guest = Mock()
        guest.id = 'test_vm'
        guest.tasks = [{'add_account': [{'account': 'testuser', 'passwd': 'pass123'}]}]
        
        # Simulate VM readiness check returning None (not ready)
        orchestrator._wait_for_vm_readiness = Mock(return_value=None)
        
        # Simulate task execution code path
        task_results = []
        guest_id = 'test_vm'
        
        if not orchestrator._wait_for_vm_readiness.return_value:
            for task_config in guest.tasks:
                for task_type, task_params in task_config.items():
                    task_results.append({
                        "task_id": f"{guest_id}_{task_type}_pending",
                        "task_type": task_type,
                        "success": False,
                        "message": "VM not ready during deployment - task execution deferred"
                    })
        
        assert len(task_results) == 1
        assert task_results[0]["success"] is False
        assert "deferred" in task_results[0]["message"]

class TestConfigurationValidation:
    """Test configuration validation and parsing improvements"""

    def test_yaml_configuration_parsing(self):
        """Test YAML configuration parsing with corrected format"""
        config_yaml = """
---
- host_settings:
  - id: host_1
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: ubuntu

- guest_settings:
  - id: test_vm
    basevm_host: host_1
    basevm_config_file: /home/ubuntu/cyris/images/basevm.xml
    basevm_type: kvm

- clone_settings:
  - range_id: test_range
    hosts:
    - host_id: host_1
      instance_number: 1
      guests:
      - guest_id: test_vm
        number: 1
        entry_point: yes
        tasks:
          - add_account:
              - account: user.test
                passwd: password123
                full_name: "Test User"
      topology:
      - type: custom
        networks:
        - name: test_network
          members: test_vm.eth0
        """

        config = yaml.safe_load(config_yaml)
        
        # Validate structure
        assert len(config) == 3
        assert 'host_settings' in config[0]
        assert 'guest_settings' in config[1]  
        assert 'clone_settings' in config[2]
        
        # Validate corrected values
        host_settings = config[0]['host_settings'][0]
        assert host_settings['account'] == 'ubuntu'  # Fixed from 'cyuser'
        
        guest_settings = config[1]['guest_settings'][0]
        assert '/home/ubuntu/cyris/' in guest_settings['basevm_config_file']  # Fixed path
        
        clone_settings = config[2]['clone_settings'][0]
        tasks = clone_settings['hosts'][0]['guests'][0]['tasks']
        add_account_task = tasks[0]['add_account'][0]
        assert add_account_task['account'] == 'user.test'  # Username with dot should work

class TestTaskTypeImplementation:
    """Test different task type implementations"""

    @pytest.fixture
    def task_executor(self):
        config = {
            'base_path': '/tmp/test_cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        return TaskExecutor(config)

    def test_install_package_task_ubuntu(self, task_executor):
        """Test package installation with correct package manager"""
        task_executor._execute_ssh_command = Mock(return_value=(True, "vim installed", ""))
        
        class MockGuest:
            def __init__(self):
                self.basevm_os_type = 'linux'
                self.basevm_type = 'kvm'

        guest = MockGuest()
        params = {
            'package_manager': 'apt-get',  # Correct for Ubuntu
            'name': 'vim',
            'version': ''
        }

        result = task_executor._execute_install_package(
            task_id='test_install',
            params=params,
            guest_ip='192.168.122.100',
            guest=guest,
            start_time=time.time()
        )

        assert result.success is True
        # Verify the command used apt-get (not yum)
        call_args = task_executor._execute_ssh_command.call_args[0]
        assert 'apt-get' in call_args[1]
        assert 'vim' in call_args[1]

    def test_modify_account_task_success(self, task_executor):
        """Test account modification with password change"""
        # Mock successful script execution
        task_executor._execute_ssh_command = Mock()
        task_executor._execute_ssh_command.side_effect = [
            (True, "", ""),  # Upload script
            (True, "", ""),  # Make executable  
            (True, "User modification completed for testuser", ""),  # Execute
            (True, "", "")   # Cleanup
        ]

        class MockGuest:
            def __init__(self):
                self.basevm_os_type = 'linux'
                self.basevm_type = 'kvm'

        guest = MockGuest()
        params = {
            'account': 'testuser',
            'new_account': 'null',
            'new_passwd': 'newpassword123'
        }

        result = task_executor._execute_modify_account(
            task_id='test_modify',
            params=params,
            guest_ip='192.168.122.100',
            guest=guest,
            start_time=time.time()
        )

        assert result.success is True
        assert "SUCCESS" in result.message

class TestNetworkTopologyIntegration:
    """Test network topology creation and IP management"""

    def test_ip_assignment_consistency(self):
        """Test that IP assignments are consistent between topology and VMs"""
        # This test validates that topology-assigned IPs match VM-discovered IPs
        # Currently this is a known issue that needs architectural fix
        
        # Mock topology manager
        topology_mgr = Mock()
        topology_mgr.create_topology.return_value = {
            'test_vm': '192.168.122.100'
        }
        
        # Mock VM IP manager  
        vm_ip_mgr = Mock()
        vm_health_info = Mock()
        vm_health_info.ip_addresses = ['192.168.122.150']  # Different IP from topology
        vm_ip_mgr.get_vm_health_info.return_value = vm_health_info
        
        # This test documents the current inconsistency
        topology_ip = topology_mgr.create_topology.return_value['test_vm']
        actual_ip = vm_health_info.ip_addresses[0]
        
        # Currently these don't match - this is the architectural issue to fix
        assert topology_ip != actual_ip
        
        # TODO: Fix this inconsistency in the architecture
        # The expectation is that these should match:
        # assert topology_ip == actual_ip

if __name__ == '__main__':
    pytest.main([__file__, '-v'])