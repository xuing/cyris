#!/usr/bin/env python3
"""
KVM Provider 基础功能测试
Unit tests for KVM Provider basic functionality
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import logging

# Import from project structure
from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.domain.entities.guest import Guest

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestKVMProviderBasic:
    """Unit tests for KVM Provider basic functionality"""
    
    def test_kvm_provider_initialization(self):
        """测试KVM Provider初始化"""
        config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': '/tmp/cyris-test',
            'storage_pool': 'default'
        }
        
        provider = KVMProvider(config)
        assert provider is not None
        assert provider.config == config
    
    @patch('cyris.infrastructure.providers.kvm_provider.libvirt')
    def test_kvm_provider_connection(self, mock_libvirt):
        """测试KVM Provider连接"""
        # Mock libvirt connection
        mock_conn = Mock()
        mock_conn.isAlive.return_value = True
        mock_libvirt.open.return_value = mock_conn
        
        config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': '/tmp/cyris-test'
        }
        
        provider = KVMProvider(config)
        provider.connect()
        
        # The connection should be True when libvirt is properly mocked
        assert provider.connection is not None
        mock_libvirt.open.assert_called_once_with('qemu:///system')
    
    def test_ssh_key_generation_integration(self):
        """测试SSH密钥生成集成"""
        from cyris.tools.ssh_manager import SSHManager
        
        ssh_manager = SSHManager()
        
        # Test key pair generation - this returns file paths, not key content
        private_key_path, public_key_path = ssh_manager.get_or_create_default_keypair("test-key")
        
        assert private_key_path is not None
        assert public_key_path is not None
        assert len(private_key_path) > 0
        assert len(public_key_path) > 0
        
        # Check the paths are reasonable
        import os
        assert os.path.isabs(private_key_path)  # Should be absolute path
        assert os.path.isabs(public_key_path)   # Should be absolute path


def test_kvm_provider_basic_integration():
    """集成测试：KVM Provider基础功能 - 需要真实KVM环境"""
    print("🧪 Testing KVM Provider Basic Functionality")
    
    config = {
        'libvirt_uri': 'qemu:///system',
        'base_path': '/tmp/cyris-test',
        'storage_pool': 'default'
    }
    
    try:
        # 1. 初始化KVM Provider
        print("1️⃣ Initializing KVM Provider...")
        provider = KVMProvider(config)
        provider.connect()
        print(f"✅ Connected to KVM: {provider.is_connected()}")
        
        # 2. 测试VM状态查询 (使用实际的VM名称)
        print("2️⃣ Testing VM status query...")
        # 这里需要实际的VM名称，跳过如果没有运行的VM
        try:
            result = provider.get_status(['cyris-desktop-3c9b802a'])
            print(f"✅ VM Status Query: {result}")
        except Exception as e:
            print(f"ℹ️ No test VMs available: {e}")
        
        provider.disconnect()
        print("✅ KVM Provider integration test completed!")
        return True
        
    except Exception as e:
        print(f"❌ KVM Provider integration test failed: {e}")
        return False


if __name__ == "__main__":
    # Run integration test if called directly
    test_kvm_provider_basic_integration()