#!/usr/bin/env python3

"""
Comprehensive tests for SSH Manager
Following TDD principles: test real functionality where possible, mock only external dependencies
"""

import pytest
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import sys
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.tools.ssh_manager import (
    SSHManager, SSHCredentials, SSHCommand, SSHResult
)


class TestSSHCredentials:
    """Test SSH credentials dataclass"""
    
    def test_credentials_creation_defaults(self):
        """Test SSH credentials with default values"""
        creds = SSHCredentials(hostname="test.example.com")
        
        assert creds.hostname == "test.example.com"
        assert creds.port == 22
        assert creds.username == "root"
        assert creds.password is None
        assert creds.private_key_path is None
        assert creds.private_key_data is None
        assert creds.timeout == 30
    
    def test_credentials_creation_custom(self):
        """Test SSH credentials with custom values"""
        creds = SSHCredentials(
            hostname="custom.example.com",
            port=2222,
            username="admin",
            password="secret123",
            private_key_path="/path/to/key",
            timeout=60
        )
        
        assert creds.hostname == "custom.example.com"
        assert creds.port == 2222
        assert creds.username == "admin"
        assert creds.password == "secret123"
        assert creds.private_key_path == "/path/to/key"
        assert creds.timeout == 60


class TestSSHCommand:
    """Test SSH command dataclass"""
    
    def test_command_creation_defaults(self):
        """Test SSH command with default values"""
        cmd = SSHCommand("echo 'test'", "Test command")
        
        assert cmd.command == "echo 'test'"
        assert cmd.description == "Test command"
        assert cmd.timeout == 300
        assert cmd.ignore_errors is False
        assert cmd.expected_return_codes == [0]
    
    def test_command_creation_custom(self):
        """Test SSH command with custom values"""
        cmd = SSHCommand(
            "ls -la",
            "List files",
            timeout=60,
            ignore_errors=True,
            expected_return_codes=[0, 1, 2]
        )
        
        assert cmd.command == "ls -la"
        assert cmd.description == "List files"
        assert cmd.timeout == 60
        assert cmd.ignore_errors is True
        assert cmd.expected_return_codes == [0, 1, 2]


class TestSSHResult:
    """Test SSH result dataclass"""
    
    def test_result_creation(self):
        """Test SSH result creation"""
        result = SSHResult(
            hostname="test.example.com",
            command="echo 'test'",
            return_code=0,
            stdout="test\n",
            stderr="",
            execution_time=0.5,
            success=True
        )
        
        assert result.hostname == "test.example.com"
        assert result.command == "echo 'test'"
        assert result.return_code == 0
        assert result.stdout == "test\n"
        assert result.stderr == ""
        assert result.execution_time == 0.5
        assert result.success is True
        assert result.error_message is None


class TestSSHManagerBasics:
    """Test SSH manager basic functionality"""
    
    @pytest.fixture
    def temp_key_dir(self):
        """Create temporary directory for SSH keys"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def ssh_manager(self, temp_key_dir):
        """Create SSH manager with temporary key directory"""
        return SSHManager(
            max_connections=10,
            connection_timeout=10,
            command_timeout=30,
            key_dir=temp_key_dir
        )
    
    def test_ssh_manager_init(self, ssh_manager, temp_key_dir):
        """Test SSH manager initialization"""
        assert ssh_manager.max_connections == 10
        assert ssh_manager.connection_timeout == 10
        assert ssh_manager.command_timeout == 30
        assert ssh_manager.key_dir == temp_key_dir
        assert temp_key_dir.exists()
        assert len(ssh_manager._connections) == 0
    
    def test_generate_ssh_keypair(self, ssh_manager):
        """Test SSH key pair generation"""
        key_name = "test_key"
        
        # Generate key pair
        private_path, public_path = ssh_manager.generate_ssh_keypair(key_name)
        
        # Check files were created
        private_key_file = Path(private_path)
        public_key_file = Path(public_path)
        
        assert private_key_file.exists()
        assert public_key_file.exists()
        assert private_key_file.name == key_name
        assert public_key_file.name == f"{key_name}.pub"
        
        # Check permissions
        assert oct(private_key_file.stat().st_mode)[-3:] == "600"
        assert oct(public_key_file.stat().st_mode)[-3:] == "644"
        
        # Check key content format
        with open(private_path, 'r') as f:
            private_content = f.read()
        with open(public_path, 'r') as f:
            public_content = f.read()
        
        assert private_content.startswith("-----BEGIN PRIVATE KEY-----")
        assert private_content.endswith("-----END PRIVATE KEY-----\n")
        assert public_content.startswith("ssh-rsa ")
    
    def test_generate_ssh_keypair_overwrite_protection(self, ssh_manager):
        """Test SSH key pair overwrite protection"""
        key_name = "existing_key"
        
        # Generate initial key pair
        ssh_manager.generate_ssh_keypair(key_name)
        
        # Try to generate again without overwrite
        with pytest.raises(ValueError, match="already exists"):
            ssh_manager.generate_ssh_keypair(key_name, overwrite=False)
        
        # Should work with overwrite=True
        private_path, public_path = ssh_manager.generate_ssh_keypair(key_name, overwrite=True)
        assert Path(private_path).exists()
        assert Path(public_path).exists()
    
    def test_get_ssh_manager_stats(self, ssh_manager):
        """Test SSH manager statistics"""
        # Generate some keys for testing
        ssh_manager.generate_ssh_keypair("key1")
        ssh_manager.generate_ssh_keypair("key2")
        
        stats = ssh_manager.get_ssh_manager_stats()
        
        assert stats["active_connections"] == 0
        assert stats["max_connections"] == 10
        assert stats["connection_timeout"] == 10
        assert stats["command_timeout"] == 30
        assert stats["available_keys"] == 2
        assert stats["connection_hosts"] == []
        assert "key_directory" in stats


class TestSSHManagerMockConnections:
    """Test SSH manager with mocked connections"""
    
    @pytest.fixture
    def temp_key_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def ssh_manager(self, temp_key_dir):
        return SSHManager(key_dir=temp_key_dir)
    
    @pytest.fixture
    def mock_credentials(self):
        return SSHCredentials(
            hostname="test.example.com",
            username="testuser",
            password="testpass"
        )
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_execute_command_success(self, mock_ssh_client_class, ssh_manager, mock_credentials):
        """Test successful command execution"""
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        
        # Setup mock command execution
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"test output\n"
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Execute command
        command = SSHCommand("echo 'test'", "Test command")
        result = ssh_manager.execute_command(mock_credentials, command)
        
        # Verify result
        assert result.hostname == "test.example.com"
        assert result.command == "echo 'test'"
        assert result.return_code == 0
        assert result.stdout == "test output\n"
        assert result.stderr == ""
        assert result.success is True
        assert result.error_message is None
        
        # Verify SSH client was called correctly
        mock_client.connect.assert_called_once()
        mock_client.exec_command.assert_called_once_with("echo 'test'", timeout=300)
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_execute_command_failure(self, mock_ssh_client_class, ssh_manager, mock_credentials):
        """Test failed command execution"""
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        
        # Setup mock command execution with failure
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"command not found\n"
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Execute command
        command = SSHCommand("nonexistent_command", "Test failing command")
        result = ssh_manager.execute_command(mock_credentials, command)
        
        # Verify result
        assert result.hostname == "test.example.com"
        assert result.command == "nonexistent_command"
        assert result.return_code == 1
        assert result.stdout == ""
        assert result.stderr == "command not found\n"
        assert result.success is False
        assert result.error_message == "command not found\n"
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_execute_command_ignore_errors(self, mock_ssh_client_class, ssh_manager, mock_credentials):
        """Test command execution with ignore_errors=True"""
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        
        # Setup mock command execution with failure
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"error\n"
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Execute command with ignore_errors=True
        command = SSHCommand("failing_command", "Test command", ignore_errors=True)
        result = ssh_manager.execute_command(mock_credentials, command)
        
        # Should still be marked as success due to ignore_errors
        assert result.success is True
        assert result.return_code == 1
        assert result.error_message is None
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_test_connection_success(self, mock_ssh_client_class, ssh_manager, mock_credentials):
        """Test successful connection test"""
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        
        # Setup mock test command
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"test\n"
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Test connection
        result = ssh_manager.test_connection(mock_credentials)
        
        assert result is True
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_test_connection_failure(self, mock_ssh_client_class, ssh_manager, mock_credentials):
        """Test failed connection test"""
        # Setup mock SSH client to raise exception
        mock_ssh_client_class.side_effect = Exception("Connection failed")
        
        # Test connection
        result = ssh_manager.test_connection(mock_credentials)
        
        assert result is False
    
    def test_close_all_connections(self, ssh_manager):
        """Test closing all connections"""
        # Add some mock connections
        mock_connection1 = MagicMock()
        mock_connection2 = MagicMock()
        
        ssh_manager._connections["host1:22:user"] = mock_connection1
        ssh_manager._connections["host2:22:user"] = mock_connection2
        
        # Close all connections
        ssh_manager.close_all_connections()
        
        # Verify connections were closed
        mock_connection1.close.assert_called_once()
        mock_connection2.close.assert_called_once()
        assert len(ssh_manager._connections) == 0


class TestSSHManagerFileOperations:
    """Test SSH manager file upload/download operations"""
    
    @pytest.fixture
    def temp_key_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def ssh_manager(self, temp_key_dir):
        return SSHManager(key_dir=temp_key_dir)
    
    @pytest.fixture
    def mock_credentials(self):
        return SSHCredentials(
            hostname="test.example.com",
            username="testuser",
            password="testpass"
        )
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_upload_file_success(self, mock_ssh_client_class, ssh_manager, mock_credentials, temp_key_dir):
        """Test successful file upload"""
        # Create a test file
        test_file = temp_key_dir / "test_file.txt"
        test_file.write_text("test content")
        
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp
        mock_ssh_client_class.return_value = mock_client
        
        # Upload file
        result = ssh_manager.upload_file(
            mock_credentials,
            str(test_file),
            "/remote/path/test_file.txt"
        )
        
        # Verify result
        assert result is True
        mock_client.open_sftp.assert_called_once()
        mock_sftp.put.assert_called_once_with(str(test_file), "/remote/path/test_file.txt")
        mock_sftp.close.assert_called_once()
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_download_file_success(self, mock_ssh_client_class, ssh_manager, mock_credentials, temp_key_dir):
        """Test successful file download"""
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp
        mock_ssh_client_class.return_value = mock_client
        
        # Download file
        local_path = temp_key_dir / "downloaded_file.txt"
        result = ssh_manager.download_file(
            mock_credentials,
            "/remote/path/file.txt",
            str(local_path)
        )
        
        # Verify result
        assert result is True
        mock_client.open_sftp.assert_called_once()
        mock_sftp.get.assert_called_once_with("/remote/path/file.txt", str(local_path))
        mock_sftp.close.assert_called_once()


class TestSSHManagerPublicKeyInstallation:
    """Test SSH public key installation"""
    
    @pytest.fixture
    def temp_key_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def ssh_manager(self, temp_key_dir):
        return SSHManager(key_dir=temp_key_dir)
    
    @pytest.fixture
    def mock_credentials(self):
        return SSHCredentials(
            hostname="test.example.com",
            username="testuser",
            password="testpass"
        )
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_install_public_key_success(self, mock_ssh_client_class, ssh_manager, mock_credentials, temp_key_dir):
        """Test successful public key installation"""
        # Generate a key pair
        private_path, public_path = ssh_manager.generate_ssh_keypair("test_key")
        
        # Setup mock SSH client
        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        
        # Mock successful command execution for all key installation steps
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Install public key
        result = ssh_manager.install_public_key(mock_credentials, public_path, "testuser")
        
        assert result is True
        
        # Should have called exec_command for each installation step
        assert mock_client.exec_command.call_count >= 4  # mkdir, chmod, echo, chmod, chown


if __name__ == "__main__":
    pytest.main([__file__, "-v"])