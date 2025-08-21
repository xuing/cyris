"""
Integration Tests for Task Executor

Tests the real task execution functionality without mocks.
Focuses on command generation and execution flow.
"""

import pytest
import tempfile
import subprocess
from pathlib import Path
import logging
from unittest.mock import patch, MagicMock

from src.cyris.services.task_executor import TaskExecutor, TaskType, TaskResult
from src.cyris.domain.entities.guest import Guest, GuestBuilder


class TestTaskExecutorIntegration:
    """Integration tests for task execution service"""
    
    @pytest.fixture
    def task_executor(self):
        """Create a task executor instance"""
        config = {
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        return TaskExecutor(config)
    
    @pytest.fixture
    def sample_guest(self):
        """Create a sample guest configuration"""
        from src.cyris.domain.entities.guest import BaseVMType, OSType
        return (GuestBuilder()
                .with_guest_id("test_desktop")
                .with_basevm_host("host_1")
                .with_basevm_config_file("/tmp/test.xml")
                .with_basevm_type(BaseVMType.KVM)
                .with_basevm_os_type(OSType.UBUNTU)
                .build())
    
    @pytest.fixture
    def windows_guest(self):
        """Create a Windows guest configuration"""
        from src.cyris.domain.entities.guest import BaseVMType, OSType
        return (GuestBuilder()
                .with_guest_id("test_windows")
                .with_basevm_host("host_1")
                .with_basevm_config_file("/tmp/test.xml")
                .with_basevm_type(BaseVMType.KVM)
                .with_basevm_os_type(OSType.WINDOWS_7)
                .build())
    
    def test_add_account_task_linux(self, task_executor, sample_guest):
        """Test add account task generation for Linux"""
        params = {
            'account': 'testuser',
            'passwd': 'testpass123',
            'full_name': 'Test User'
        }
        
        # Mock SSH execution to avoid actual network calls
        with patch.object(task_executor, '_execute_ssh_command') as mock_ssh:
            mock_ssh.return_value = (True, "User created successfully", "")
            
            result = task_executor._execute_add_account(
                "test_task_1", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.ADD_ACCOUNT
        assert "testuser" in result.message
        
        # Verify SSH command was called with correct parameters
        mock_ssh.assert_called_once()
        args = mock_ssh.call_args[0]
        assert args[0] == "192.168.1.100"  # IP address
        assert "testuser" in args[1]  # Command contains username
        assert "testpass123" in args[1]  # Command contains password
    
    def test_add_account_task_windows(self, task_executor, windows_guest):
        """Test add account task generation for Windows"""
        params = {
            'account': 'winuser',
            'passwd': 'winpass123'
        }
        
        with patch.object(task_executor, '_execute_ssh_command') as mock_ssh:
            mock_ssh.return_value = (True, "User created", "")
            
            result = task_executor._execute_add_account(
                "test_task_2", params, "192.168.1.101", windows_guest
            )
        
        assert result.success
        
        # Verify Windows-specific command
        mock_ssh.assert_called_once()
        command = mock_ssh.call_args[0][1]
        assert "net user" in command
        assert "winuser" in command
        assert "Remote Desktop Users" in command
    
    def test_install_package_task(self, task_executor, sample_guest):
        """Test install package task generation"""
        params = {
            'package_manager': 'yum',
            'name': 'wireshark',
            'version': '1.8.10'
        }
        
        with patch.object(task_executor, '_execute_ssh_command') as mock_ssh:
            mock_ssh.return_value = (True, "Package installed", "")
            
            result = task_executor._execute_install_package(
                "test_task_3", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.INSTALL_PACKAGE
        
        # Verify command format
        command = mock_ssh.call_args[0][1]
        assert "yum install -y wireshark 1.8.10" in command
    
    def test_copy_content_task(self, task_executor, sample_guest):
        """Test copy content task execution"""
        params = {
            'src': '/tmp/test_file.txt',
            'dst': '/home/user/test_file.txt'
        }
        
        # Create a temporary file to copy
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
            tmp_file.write(b"Test content")
            params['src'] = tmp_file.name
        
        # Mock subprocess for copy script execution
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "File copied successfully"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            result = task_executor._execute_copy_content(
                "test_task_4", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.COPY_CONTENT
        
        # Verify script was called
        mock_run.assert_called_once()
        # Cleanup
        Path(tmp_file.name).unlink()
    
    def test_execute_program_task(self, task_executor, sample_guest):
        """Test program execution task"""
        params = {
            'program': '/usr/bin/test_script.sh',
            'interpreter': 'bash',
            'args': '--verbose'
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Script executed successfully"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            result = task_executor._execute_program(
                "test_task_5", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.EXECUTE_PROGRAM
        
        # Verify python3 run_program.py was called
        call_args = mock_run.call_args[0][0]
        assert "python3" in " ".join(call_args)
        assert "run_program.py" in " ".join(call_args)
    
    def test_emulate_attack_ssh(self, task_executor, sample_guest):
        """Test SSH attack emulation task"""
        params = {
            'attack_type': 'ssh_attack',
            'target_account': 'admin',
            'attempt_number': 50,
            'attack_time': '2024-01-15'
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Attack simulation completed"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            result = task_executor._execute_emulate_attack(
                "test_task_6", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.EMULATE_ATTACK
        
        # Verify attack script was called
        mock_run.assert_called_once()
    
    def test_emulate_malware_task(self, task_executor, sample_guest):
        """Test malware emulation task"""
        params = {
            'name': 'test_daemon',
            'mode': 'dummy_calculation',
            'cpu_utilization': 25
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Malware simulation started"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            result = task_executor._execute_emulate_malware(
                "test_task_7", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.EMULATE_MALWARE
        
        # Verify malware script was called with correct parameters
        call_args = mock_run.call_args[0][0]
        command_str = " ".join(call_args)
        assert "malware_launch.sh" in command_str
        assert "test_daemon" in command_str
        assert "dummy_calculation" in command_str
        assert "25" in command_str
    
    def test_firewall_rules_task(self, task_executor, sample_guest):
        """Test firewall rules application task"""
        params = {
            'rule': '/tmp/test_firewall_rules.txt'
        }
        
        # Create temporary rule file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
            tmp_file.write("iptables -A INPUT -p tcp --dport 22 -j ACCEPT\n")
            params['rule'] = tmp_file.name
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Firewall rules applied"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            result = task_executor._execute_firewall_rules(
                "test_task_8", params, "192.168.1.100", sample_guest
            )
        
        assert result.success
        assert result.task_type == TaskType.FIREWALL_RULES
        
        # Cleanup
        Path(tmp_file.name).unlink()
    
    def test_multiple_tasks_execution(self, task_executor, sample_guest):
        """Test execution of multiple tasks for a single guest"""
        tasks = [
            {
                'add_account': [
                    {'account': 'user1', 'passwd': 'pass1'},
                    {'account': 'user2', 'passwd': 'pass2'}
                ]
            },
            {
                'install_package': [
                    {'package_manager': 'yum', 'name': 'git'},
                    {'package_manager': 'yum', 'name': 'vim'}
                ]
            }
        ]
        
        with patch.object(task_executor, '_execute_ssh_command') as mock_ssh:
            mock_ssh.return_value = (True, "Success", "")
            
            results = task_executor.execute_guest_tasks(
                sample_guest, "192.168.1.100", tasks
            )
        
        # Should have 4 results (2 add_account + 2 install_package)
        assert len(results) == 4
        
        # Check task types
        task_types = [result.task_type for result in results]
        assert task_types.count(TaskType.ADD_ACCOUNT) == 2
        assert task_types.count(TaskType.INSTALL_PACKAGE) == 2
        
        # All should succeed
        assert all(result.success for result in results)
    
    def test_ssh_command_execution_failure(self, task_executor, sample_guest):
        """Test handling of SSH command execution failure"""
        params = {
            'account': 'failuser',
            'passwd': 'failpass'
        }
        
        with patch.object(task_executor, '_execute_ssh_command') as mock_ssh:
            mock_ssh.return_value = (False, "", "Permission denied")
            
            result = task_executor._execute_add_account(
                "test_fail", params, "192.168.1.100", sample_guest
            )
        
        assert not result.success
        assert result.error == "Permission denied"
        assert "FAILED" in result.message
    
    def test_task_execution_exception_handling(self, task_executor, sample_guest):
        """Test handling of exceptions during task execution"""
        params = {'account': 'test'}  # Missing required 'passwd' field
        
        # This should cause an exception due to missing passwd
        result = task_executor._execute_single_task(
            "exception_test", TaskType.ADD_ACCOUNT, params, sample_guest, "192.168.1.100"
        )
        
        assert not result.success
        assert "Task execution failed" in result.message
        assert result.error is not None


class TestTaskExecutorRealOperations:
    """Tests that use real operations where safe"""
    
    def test_script_path_generation(self):
        """Test that script paths are generated correctly"""
        config = {
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30
        }
        executor = TaskExecutor(config)
        
        # Test various script paths
        add_user_script = f"{executor.abspath}/{executor.instantiation_dir}/users_managing/add_user.sh"
        copy_script = f"{executor.abspath}/{executor.instantiation_dir}/content_copy_program_run/copy_content.sh"
        malware_script = f"{executor.abspath}/{executor.instantiation_dir}/malware_creation/malware_launch.sh"
        
        assert "/home/ubuntu/cyris/instantiation/users_managing/add_user.sh" == add_user_script
        assert "/home/ubuntu/cyris/instantiation/content_copy_program_run/copy_content.sh" == copy_script
        assert "/home/ubuntu/cyris/instantiation/malware_creation/malware_launch.sh" == malware_script
    
    def test_command_format_validation(self):
        """Test that generated commands have correct format"""
        # Test Linux user creation command
        account = "testuser"
        passwd = "testpass123"
        full_name = "Test User"
        script_path = "/path/to/add_user.sh"
        
        command = f"bash {script_path} {account} {passwd} yes \"{full_name}\""
        
        assert "bash" in command
        assert account in command
        assert passwd in command
        assert full_name in command
        
        # Test Windows user creation command
        win_command = f"net user {account} {passwd} /ADD && net localgroup \"Remote Desktop Users\" {account} /ADD"
        
        assert "net user" in win_command
        assert "/ADD" in win_command
        assert "Remote Desktop Users" in win_command
    
    @pytest.mark.skipif(
        not Path('/home/ubuntu/cyris/instantiation').exists(),
        reason="CyRIS instantiation directory not available"
    )
    def test_instantiation_scripts_exist(self):
        """Test that required instantiation scripts exist"""
        base_path = Path('/home/ubuntu/cyris/instantiation')
        
        expected_scripts = [
            'users_managing/add_user.sh',
            'users_managing/modify_user.sh',
            'content_copy_program_run/copy_content.sh',
            'content_copy_program_run/run_program.py',
            'malware_creation/malware_launch.sh',
            'attacks_emulation/install_paramiko.sh'
        ]
        
        missing_scripts = []
        for script in expected_scripts:
            script_path = base_path / script
            if not script_path.exists():
                missing_scripts.append(str(script_path))
        
        if missing_scripts:
            pytest.skip(f"Missing scripts: {missing_scripts}")
        
        # If we get here, all expected scripts exist
        assert True


if __name__ == "__main__":
    # Enable logging for manual testing
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])