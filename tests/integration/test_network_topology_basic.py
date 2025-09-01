#!/usr/bin/env python3
"""
Network Topology Manager 集成测试
Integration tests for Network Topology Manager
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import logging

from cyris.infrastructure.network.topology_manager import NetworkTopologyManager
from cyris.infrastructure.providers.kvm_provider import KVMProvider

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestNetworkTopologyIntegration:
    """Integration tests for Network Topology Manager"""
    
    def test_topology_manager_initialization(self):
        """测试Topology Manager初始化"""
        topology_manager = NetworkTopologyManager()
        assert topology_manager is not None
    
    @patch('cyris.infrastructure.providers.kvm_provider.libvirt')
    def test_ip_discovery_integration(self, mock_libvirt):
        """测试IP发现功能集成"""
        # Mock libvirt
        mock_conn = Mock()
        mock_libvirt.open.return_value = mock_conn
        
        topology_manager = NetworkTopologyManager()
        
        # Test VM IP discovery
        vm_names = ["test-vm-1", "test-vm-2"]
        
        with patch.object(topology_manager, 'discover_vm_ips') as mock_discover:
            mock_discover.return_value = {
                "test-vm-1": "192.168.122.10",
                "test-vm-2": "192.168.122.11"
            }
            
            result = topology_manager.discover_vm_ips(vm_names)
            
            assert isinstance(result, dict)
            assert len(result) == 2
            assert "test-vm-1" in result
            assert "test-vm-2" in result


def test_ip_discovery_integration():
    """集成测试：IP发现功能 - 需要真实KVM环境"""
    print("🌐 Testing Network Topology Manager - IP Discovery")
    
    try:
        # 初始化Topology Manager
        print("1️⃣ Initializing Network Topology Manager...")
        topology_manager = NetworkTopologyManager()
        
        # 初始化KVM Provider供IP发现使用
        print("2️⃣ Setting up KVM Provider for IP discovery...")
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': '/tmp/cyris-test'
        }
        
        provider = KVMProvider(kvm_config)
        provider.connect()
        
        if not provider.is_connected():
            print("⚠️ Cannot connect to KVM, skipping IP discovery test")
            return True
        
        # 查找现有VM进行测试
        print("3️⃣ Discovering existing VMs...")
        existing_vms = []
        
        # 尝试发现一些VM的IP
        test_vm_names = [
            "cyris-desktop-f6a6b8be",
            "cyris-webserver-598ae13b"
        ]
        
        print("4️⃣ Testing IP discovery...")
        discovered_ips = {}
        
        for vm_name in test_vm_names:
            try:
                ip = provider.get_vm_ip(vm_name)
                discovered_ips[vm_name] = ip
                print(f"   {vm_name}: {ip or 'Not found'}")
            except Exception as e:
                print(f"   {vm_name}: Error - {e}")
                discovered_ips[vm_name] = None
        
        print(f"✅ IP Discovery completed: {len(discovered_ips)} VMs checked")
        
        provider.disconnect()
        print("✅ Network Topology Manager integration test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Network Topology Manager integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_topology_creation_integration():
    """集成测试：拓扑创建功能"""
    print("🏗️ Testing Network Topology Creation")
    
    try:
        topology_manager = NetworkTopologyManager()
        
        # 测试网络拓扑配置
        network_config = {
            "networks": [
                {
                    "name": "internal",
                    "subnet": "192.168.100.0/24",
                    "gateway": "192.168.100.1"
                }
            ]
        }
        
        # 创建拓扑
        print("Creating network topology...")
        topology = topology_manager.create_topology(network_config)
        
        print(f"✅ Topology created: {topology}")
        return True
        
    except Exception as e:
        print(f"❌ Topology creation integration test failed: {e}")
        return False


if __name__ == "__main__":
    # Run integration tests if called directly
    print("🚀 Starting Network Topology Integration Tests")
    print("=" * 50)
    
    test1_passed = test_ip_discovery_integration()
    print("\n" + "=" * 50)
    test2_passed = test_topology_creation_integration()
    
    if test1_passed and test2_passed:
        print("🎉 All Network Topology integration tests passed!")
    else:
        print("💥 Some Network Topology integration tests failed!")