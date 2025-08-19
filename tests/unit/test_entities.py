"""
测试实体模块
"""
import pytest
import os
import sys

# 添加main目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../main'))

from entities import Host, Guest, Bridge, CloneGuest, Command


class TestHost:
    """主机实体测试类"""

    def test_host_creation(self):
        """测试主机创建"""
        host = Host("host_1", "192.168.1.1", "192.168.122.1", "cyuser")
        
        assert host.host_id == "host_1"
        assert host.mgmt_addr == "192.168.1.1"
        assert host.virbr_addr == "192.168.122.1"
        assert host.account == "cyuser"

    def test_host_string_representation(self):
        """测试主机字符串表示"""
        host = Host("host_1", "192.168.1.1", "192.168.122.1", "cyuser")
        str_repr = str(host)
        
        assert "host_1" in str_repr
        assert "192.168.1.1" in str_repr


class TestGuest:
    """虚拟机实体测试类"""

    def test_guest_creation(self):
        """测试虚拟机创建"""
        guest = Guest("desktop", "host_1", "/path/to/basevm.xml", "kvm")
        
        assert guest.guest_id == "desktop"
        assert guest.basevm_host == "host_1"
        assert guest.basevm_config_file == "/path/to/basevm.xml"
        assert guest.basevm_type == "kvm"

    def test_guest_with_optional_fields(self):
        """测试包含可选字段的虚拟机"""
        guest = Guest("desktop", "host_1", "/path/to/basevm.xml", "kvm")
        
        # 测试可选字段的默认值
        assert hasattr(guest, 'guest_id')
        assert hasattr(guest, 'basevm_host')


class TestBridge:
    """网络桥接测试类"""

    def test_bridge_creation(self):
        """测试网络桥接创建"""
        bridge = Bridge("office", "192.168.100.0/24")
        
        assert bridge.name == "office"
        assert bridge.subnet == "192.168.100.0/24"


class TestCloneGuest:
    """克隆虚拟机测试类"""

    def test_clone_guest_creation(self):
        """测试克隆虚拟机创建"""
        clone_guest = CloneGuest("desktop", 1, True)
        
        assert clone_guest.guest_id == "desktop"
        assert clone_guest.number == 1
        assert clone_guest.entry_point is True

    def test_clone_guest_without_entry_point(self):
        """测试非入口点的克隆虚拟机"""
        clone_guest = CloneGuest("server", 2, False)
        
        assert clone_guest.guest_id == "server"
        assert clone_guest.number == 2
        assert clone_guest.entry_point is False


class TestCommand:
    """命令对象测试类"""

    def test_command_creation(self):
        """测试命令创建"""
        cmd = Command("ls -la", "List files in directory")
        
        assert cmd.command == "ls -la"
        assert cmd.description == "List files in directory"

    def test_command_string_representation(self):
        """测试命令字符串表示"""
        cmd = Command("echo 'hello'", "Print hello")
        str_repr = str(cmd)
        
        assert "echo 'hello'" in str_repr
        assert "Print hello" in str_repr