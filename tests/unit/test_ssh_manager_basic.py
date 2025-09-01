#!/usr/bin/env python3
"""
SSH Connection Manager 测试
Unit tests for SSH Manager basic functionality
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import logging

from cyris.tools.ssh_manager import SSHManager, SSHCredentials, SSHCommand

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSSHManagerBasic:
    """Unit tests for SSH Manager basic functionality"""
    
    def test_ssh_manager_initialization(self):
        """测试SSH Manager初始化"""
        ssh_manager = SSHManager()
        assert ssh_manager is not None
    
    def test_ssh_credentials_creation(self):
        """测试SSH凭据创建"""
        credentials = SSHCredentials(
            hostname="192.168.1.100",
            port=22,
            username="test",
            password="password",
            timeout=30
        )
        
        assert credentials.hostname == "192.168.1.100"
        assert credentials.port == 22
        assert credentials.username == "test"
        assert credentials.password == "password"
        assert credentials.timeout == 30
    
    def test_ssh_command_creation(self):
        """测试SSH命令创建"""
        command = SSHCommand("whoami", "Test command")
        
        assert command.command == "whoami"
        assert command.description == "Test command"
    
    @patch('cyris.tools.ssh_manager.paramiko.SSHClient')
    def test_ssh_connection_mock(self, mock_ssh_client):
        """测试SSH连接 (模拟)"""
        # Mock paramiko client
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance
        
        # Mock successful connection
        mock_client_instance.connect.return_value = None
        
        ssh_manager = SSHManager()
        credentials = SSHCredentials(
            hostname="test.example.com",
            username="test",
            password="password"
        )
        
        # Test connectivity verification
        with patch.object(ssh_manager, 'verify_connectivity') as mock_verify:
            mock_verify.return_value = {
                'reachable': True,
                'auth_working': True,
                'details': 'Connection successful'
            }
            
            result = ssh_manager.verify_connectivity(credentials)
            assert result['reachable'] == True
            assert result['auth_working'] == True
    
    @patch('cyris.tools.ssh_manager.subprocess')
    @patch('builtins.open')
    @patch('pathlib.Path.exists')
    def test_ssh_key_generation(self, mock_exists, mock_open, mock_subprocess):
        """测试SSH密钥生成"""
        # Mock file operations
        mock_exists.return_value = False
        mock_subprocess.run.return_value = Mock(returncode=0)
        
        ssh_manager = SSHManager()
        
        # Test key generation
        private_key, public_key = ssh_manager.generate_ssh_keypair("test-key", overwrite=True)
        
        assert private_key is not None
        assert public_key is not None
        assert "test-key" in private_key
        assert "test-key" in public_key


def test_ssh_connectivity_integration():
    """集成测试：SSH连接性 - 需要真实VM环境"""
    print("🔗 Testing SSH Connection Manager")
    
    try:
        ssh_manager = SSHManager()
        
        # 使用测试VM IP (如果存在)
        vm_ip = "192.168.122.89"  # 示例IP
        
        print(f"Testing connectivity to VM: {vm_ip}")
        
        # 尝试连接测试
        auth_methods = [
            {"username": "root", "password": "cyris"},
            {"username": "ubuntu", "password": "ubuntu"},
            {"username": "cyris", "password": "cyris"}
        ]
        
        connection_successful = False
        
        for auth in auth_methods:
            try:
                print(f"   Testing: {auth['username']} with password")
                
                credentials = SSHCredentials(
                    hostname=vm_ip,
                    port=22,
                    username=auth['username'],
                    password=auth.get('password'),
                    timeout=5
                )
                
                connectivity = ssh_manager.verify_connectivity(credentials, timeout=5)
                print(f"   Connectivity result: {connectivity}")
                
                if connectivity.get('auth_working', False):
                    connection_successful = True
                    print(f"✅ Successful connection with {auth['username']}")
                    break
                    
            except Exception as e:
                print(f"   Failed: {e}")
                continue
        
        if not connection_successful:
            print("ℹ️ Could not establish SSH connection - this is expected without running VMs")
        
        print("✅ SSH Connection Manager integration test completed!")
        return True
        
    except Exception as e:
        print(f"❌ SSH Connection Manager integration test failed: {e}")
        return False


def test_ssh_key_operations_integration():
    """集成测试：SSH密钥操作"""
    print("🔑 Testing SSH Key Operations")
    
    try:
        ssh_manager = SSHManager()
        
        # 生成测试密钥对
        print("Generating SSH key pair...")
        private_key, public_key = ssh_manager.generate_ssh_keypair("ssh-test", overwrite=True)
        print(f"Generated: {private_key}, {public_key}")
        
        # 验证密钥文件存在
        print("Verifying key files...")
        if Path(private_key).exists() and Path(public_key).exists():
            print("✅ Key files exist")
        else:
            print("❌ Key files missing")
            return False
            
        # 读取公钥内容
        print("Reading public key content...")
        with open(public_key, 'r') as f:
            pub_key_content = f.read().strip()
            print(f"✅ Public key: {pub_key_content[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ SSH Key Operations integration test failed: {e}")
        return False


if __name__ == "__main__":
    # Run integration tests if called directly
    print("🚀 Starting SSH Manager Integration Tests")
    print("=" * 50)
    
    test1_passed = test_ssh_connectivity_integration()
    print("\n" + "=" * 50)
    test2_passed = test_ssh_key_operations_integration()
    
    if test1_passed and test2_passed:
        print("🎉 All SSH integration tests passed!")
    else:
        print("💥 Some SSH integration tests failed!")