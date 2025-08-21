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
        host = Host("host_1", "192.168.122.1", "192.168.1.1", "cyuser")
        
        assert host.host_id == "host_1"
        assert host.virbr_addr == "192.168.122.1"
        assert host.mgmt_addr == "192.168.1.1"
        assert host.account == "cyuser"

    def test_host_string_representation(self):
        """测试主机字符串表示"""
        host = Host("host_1", "192.168.122.1", "192.168.1.1", "cyuser")
        str_repr = str(host)
        
        assert "host_1" in str_repr
        assert "192.168.1.1" in str_repr


class TestGuest:
    """虚拟机实体测试类"""

    def test_guest_creation(self):
        """测试虚拟机创建"""
        guest = Guest("desktop", "192.168.1.100", "password", "host_1", "/path/to/basevm.xml", "linux", "qcow2", "desktop_vm", [])
        
        assert guest.guest_id == "desktop"
        assert guest.basevm_addr == "192.168.1.100"
        assert guest.root_passwd == "password"
        assert guest.basevm_host == "host_1"
        assert guest.basevm_config_file == "/path/to/basevm.xml"
        assert guest.basevm_os_type == "linux"
        assert guest.basevm_type == "qcow2"
        assert guest.basevm_name == "desktop_vm"
        assert guest.tasks == []

    def test_guest_with_optional_fields(self):
        """测试包含可选字段的虚拟机"""
        guest = Guest("desktop", "192.168.1.100", "password", "host_1", "/path/to/basevm.xml", "linux", "qcow2", "desktop_vm", ["task1", "task2"])
        
        # 测试可选字段的默认值
        assert hasattr(guest, 'guest_id')
        assert hasattr(guest, 'basevm_host')
        assert len(guest.tasks) == 2


class TestBridge:
    """网络桥接测试类"""

    def test_bridge_creation(self):
        """测试网络桥接创建"""
        bridge = Bridge("office", "192.168.100.0/24")
        
        assert bridge.bridge_id == "office"
        assert bridge.addr == "192.168.100.0/24"


class TestCloneGuest:
    """克隆虚拟机测试类"""

    def test_clone_guest_creation(self):
        """测试克隆虚拟机创建"""
        clone_guest = CloneGuest("desktop", 1, 123, 456, True, [], True, "linux")
        
        assert clone_guest.guest_id == "desktop"
        assert clone_guest.index == 1
        assert clone_guest.up_instance == 123
        assert clone_guest.up_cyberrange == 456
        assert clone_guest.has_fw_setup is True
        assert clone_guest.is_entry_point is True
        assert clone_guest.os_type == "linux"

    def test_clone_guest_without_entry_point(self):
        """测试非入口点的克隆虚拟机"""
        clone_guest = CloneGuest("server", 2, 124, 456, False, ["rule1"], False, "windows")
        
        assert clone_guest.guest_id == "server"
        assert clone_guest.index == 2
        assert clone_guest.up_instance == 124
        assert clone_guest.has_fw_setup is False
        assert clone_guest.is_entry_point is False
        assert clone_guest.os_type == "windows"


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