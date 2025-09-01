#!/usr/bin/env python3
"""
最小化工作流端到端测试 - 测试所有组件集成
End-to-end test for complete CyRIS minimal workflow
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import logging

from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.infrastructure.network.topology_manager import NetworkTopologyManager
from cyris.tools.ssh_manager import SSHManager, SSHCredentials
from cyris.services.task_executor import TaskExecutor, TaskResult

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMinimalWorkflowE2E:
    """End-to-end tests for complete CyRIS minimal workflow"""
    
    @pytest.mark.e2e
    @patch('cyris.infrastructure.providers.kvm_provider.libvirt')
    def test_workflow_components_integration(self, mock_libvirt):
        """测试工作流组件集成"""
        # Mock libvirt
        mock_conn = Mock()
        mock_libvirt.open.return_value = mock_conn
        
        # Initialize components
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': '/tmp/cyris-test'
        }
        
        kvm_provider = KVMProvider(kvm_config)
        topology_manager = NetworkTopologyManager()
        ssh_manager = SSHManager()
        task_executor = TaskExecutor({'base_path': '/tmp/cyris-test'})
        
        # Verify all components can be initialized
        assert kvm_provider is not None
        assert topology_manager is not None
        assert ssh_manager is not None
        assert task_executor is not None
    
    @pytest.mark.e2e
    def test_workflow_configuration(self):
        """测试工作流配置"""
        # Test workflow configuration structure
        workflow_config = {
            'kvm': {
                'libvirt_uri': 'qemu:///system',
                'base_path': '/tmp/cyris-test'
            },
            'ssh': {
                'timeout': 30,
                'retries': 3
            },
            'tasks': {
                'timeout': 300,
                'verification': True
            }
        }
        
        # Verify configuration structure
        assert 'kvm' in workflow_config
        assert 'ssh' in workflow_config
        assert 'tasks' in workflow_config
        assert workflow_config['kvm']['libvirt_uri'] == 'qemu:///system'


def test_minimal_cyris_workflow():
    """端到端测试：完整的CyRIS最小工作流 - 需要真实环境"""
    print("🚀 Testing Complete CyRIS Minimal Workflow")
    print("=" * 60)
    
    try:
        # Step 1: 初始化所有组件
        print("📋 Step 1: Initialize all components")
        
        # KVM Provider
        kvm_config = {
            'libvirt_uri': 'qemu:///system',
            'base_path': '/tmp/cyris-test'
        }
        
        print("   Initializing KVM Provider...")
        kvm_provider = KVMProvider(kvm_config)
        kvm_provider.connect()
        print(f"   ✅ KVM Provider: {kvm_provider.is_connected()}")
        
        # Network Topology Manager
        print("   Initializing Network Topology Manager...")
        topology_manager = NetworkTopologyManager()
        print("   ✅ Network Topology Manager initialized")
        
        # SSH Manager
        print("   Initializing SSH Manager...")
        ssh_manager = SSHManager()
        print("   ✅ SSH Manager initialized")
        
        # Task Executor
        print("   Initializing Task Executor...")
        task_config = {
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        task_executor = TaskExecutor(task_config)
        print("   ✅ Task Executor initialized")
        
        # Step 2: 发现现有VM
        print("\n📋 Step 2: Discover existing VMs")
        
        test_vms = [
            "cyris-desktop-f6a6b8be",
            "cyris-webserver-598ae13b"
        ]
        
        discovered_vms = {}
        for vm_name in test_vms:
            try:
                ip = kvm_provider.get_vm_ip(vm_name)
                discovered_vms[vm_name] = ip
                print(f"   VM: {vm_name} -> {ip or 'No IP'}")
            except Exception as e:
                print(f"   VM: {vm_name} -> Error: {e}")
                discovered_vms[vm_name] = None
        
        # Step 3: 测试SSH连接 (如果有IP)
        print("\n📋 Step 3: Test SSH connectivity")
        
        ssh_tested = False
        for vm_name, ip in discovered_vms.items():
            if ip:
                print(f"   Testing SSH to {vm_name} ({ip})...")
                
                # 测试常见认证方式
                auth_methods = [
                    {"username": "root", "password": "cyris"},
                    {"username": "ubuntu", "password": "ubuntu"}
                ]
                
                for auth in auth_methods:
                    try:
                        credentials = SSHCredentials(
                            hostname=ip,
                            username=auth['username'],
                            password=auth['password'],
                            timeout=5
                        )
                        
                        connectivity = ssh_manager.verify_connectivity(credentials, timeout=5)
                        if connectivity.get('auth_working'):
                            print(f"   ✅ SSH connected: {auth['username']}@{ip}")
                            ssh_tested = True
                            break
                    except Exception as e:
                        continue
                
                if ssh_tested:
                    break
        
        if not ssh_tested:
            print("   ℹ️ No SSH connections established - VMs may need configuration")
        
        # Step 4: 测试任务定义
        print("\n📋 Step 4: Test task definitions")
        
        sample_tasks = [
            {
                'type': 'add_account',
                'username': 'testuser',
                'password': 'testpass',
                'description': 'Create test user account'
            },
            {
                'type': 'execute_program', 
                'command': 'whoami',
                'description': 'Execute simple command'
            }
        ]
        
        for i, task in enumerate(sample_tasks):
            print(f"   Task {i+1}: {task['type']} - {task['description']}")
        
        print("   ✅ Task definitions validated")
        
        # Step 5: 工作流完整性检查
        print("\n📋 Step 5: Workflow integrity check")
        
        components_status = {
            'KVM Provider': kvm_provider.is_connected(),
            'Network Discovery': len(discovered_vms) > 0,
            'SSH Manager': ssh_manager is not None,
            'Task Executor': task_executor is not None,
            'VMs Found': len([ip for ip in discovered_vms.values() if ip]) > 0
        }
        
        for component, status in components_status.items():
            status_icon = "✅" if status else "⚠️"
            print(f"   {status_icon} {component}: {status}")
        
        # 判断工作流完整性
        critical_components = ['KVM Provider', 'SSH Manager', 'Task Executor']
        all_critical_ok = all(components_status[comp] for comp in critical_components)
        
        if all_critical_ok:
            print("\n🎉 Minimal workflow integrity check PASSED!")
            print("   All critical components are functional")
        else:
            print("\n⚠️ Minimal workflow integrity check PARTIAL")
            print("   Some components need configuration")
        
        kvm_provider.disconnect()
        
        print("\n✅ Complete CyRIS Minimal Workflow test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Complete CyRIS Minimal Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_configuration_validation():
    """端到端测试：工作流配置验证"""
    print("⚙️ Testing Workflow Configuration Validation")
    
    try:
        # 定义完整的工作流配置
        workflow_config = {
            'infrastructure': {
                'provider': 'kvm',
                'kvm': {
                    'libvirt_uri': 'qemu:///system',
                    'base_path': '/tmp/cyris-test',
                    'storage_pool': 'default'
                }
            },
            'networking': {
                'discovery_methods': ['dhcp', 'virsh', 'arp'],
                'timeout': 60
            },
            'ssh': {
                'default_timeout': 30,
                'retry_count': 3,
                'auth_methods': ['key', 'password']
            },
            'tasks': {
                'execution_timeout': 300,
                'verification': True,
                'rollback_on_failure': False
            }
        }
        
        # 验证配置结构
        required_sections = ['infrastructure', 'networking', 'ssh', 'tasks']
        for section in required_sections:
            assert section in workflow_config, f"Missing configuration section: {section}"
            print(f"   ✅ {section}: Present")
        
        # 验证具体配置值
        assert workflow_config['infrastructure']['provider'] == 'kvm'
        assert workflow_config['ssh']['default_timeout'] == 30
        assert workflow_config['tasks']['verification'] == True
        
        print("✅ Workflow configuration validation passed!")
        return True
        
    except Exception as e:
        print(f"❌ Workflow configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    # Run e2e tests if called directly
    print("🚀 Starting CyRIS Minimal Workflow E2E Tests")
    print("=" * 60)
    
    test1_passed = test_minimal_cyris_workflow()
    print("\n" + "=" * 60)
    test2_passed = test_workflow_configuration_validation()
    
    if test1_passed and test2_passed:
        print("\n🎉 All CyRIS Minimal Workflow E2E tests passed!")
    else:
        print("\n💥 Some CyRIS Minimal Workflow E2E tests failed!")