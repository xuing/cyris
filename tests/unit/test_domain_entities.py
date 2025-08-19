"""
测试现代化领域实体
"""
import pytest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.domain.entities.host import Host, HostBuilder
from cyris.domain.entities.guest import Guest, GuestBuilder, OSType, BaseVMType


class TestHost:
    """测试主机实体"""

    def test_host_creation(self):
        """测试主机创建"""
        host = Host(
            host_id="test_host",
            mgmt_addr="192.168.1.1",
            virbr_addr="192.168.122.1",
            account="cyuser"
        )
        
        assert host.host_id == "test_host"
        assert host.mgmt_addr == "192.168.1.1"
        assert host.virbr_addr == "192.168.122.1"
        assert host.account == "cyuser"

    def test_host_methods(self):
        """测试主机方法"""
        host = Host(
            host_id="test_host",
            mgmt_addr="192.168.1.1",
            virbr_addr="192.168.122.1",
            account="cyuser"
        )
        
        assert host.get_host_id() == "test_host"
        assert host.get_mgmt_addr() == "192.168.1.1"
        assert host.get_virbr_addr() == "192.168.122.1"
        assert host.get_account() == "cyuser"

    def test_host_string_representation(self):
        """测试主机字符串表示"""
        host = Host(
            host_id="test_host",
            mgmt_addr="192.168.1.1",
            virbr_addr="192.168.122.1",
            account="cyuser"
        )
        
        str_repr = str(host)
        assert "test_host" in str_repr
        assert "192.168.1.1" in str_repr

    def test_host_ip_validation(self):
        """测试IP地址验证"""
        # 有效IP地址
        host = Host(
            host_id="test_host",
            mgmt_addr="192.168.1.1",
            virbr_addr="192.168.122.1",
            account="cyuser"
        )
        assert host.mgmt_addr == "192.168.1.1"
        
        # 主机名也应该被接受
        host = Host(
            host_id="test_host",
            mgmt_addr="localhost",
            virbr_addr="192.168.122.1",
            account="cyuser"
        )
        assert host.mgmt_addr == "localhost"


class TestHostBuilder:
    """测试主机构建器"""

    def test_host_builder(self):
        """测试主机构建器"""
        host = (HostBuilder()
                .with_host_id("test_host")
                .with_mgmt_addr("192.168.1.1")
                .with_virbr_addr("192.168.122.1")
                .with_account("cyuser")
                .build())
        
        assert host.host_id == "test_host"
        assert host.mgmt_addr == "192.168.1.1"
        assert host.virbr_addr == "192.168.122.1"
        assert host.account == "cyuser"

    def test_host_builder_missing_fields(self):
        """测试主机构建器缺少字段"""
        builder = HostBuilder().with_host_id("test_host")
        
        with pytest.raises(ValueError, match="Missing required fields"):
            builder.build()


class TestGuest:
    """测试虚拟机实体"""

    def test_guest_creation(self):
        """测试虚拟机创建"""
        guest = Guest(
            guest_id="test_guest",
            basevm_addr="192.168.1.100",
            root_passwd="password",
            basevm_host="test_host",
            basevm_config_file="/path/to/vm.xml",
            basevm_os_type=OSType.UBUNTU,
            basevm_type=BaseVMType.KVM,
            basevm_name="test_vm",
            tasks=[]
        )
        
        assert guest.guest_id == "test_guest"
        assert guest.basevm_addr == "192.168.1.100"
        assert guest.basevm_host == "test_host"
        assert guest.basevm_os_type == OSType.UBUNTU
        assert guest.basevm_type == BaseVMType.KVM

    def test_guest_methods(self):
        """测试虚拟机方法"""
        guest = Guest(
            guest_id="test_guest",
            basevm_addr="192.168.1.100",
            root_passwd="password",
            basevm_host="test_host",
            basevm_config_file="/path/to/vm.xml",
            basevm_os_type=OSType.UBUNTU,
            basevm_type=BaseVMType.KVM,
            basevm_name="test_vm",
            tasks=[]
        )
        
        assert guest.get_guest_id() == "test_guest"
        assert guest.get_basevm_addr() == "192.168.1.100"
        assert guest.get_basevm_host() == "test_host"
        
        # 测试设置方法
        guest.set_basevm_addr("192.168.1.200")
        assert guest.get_basevm_addr() == "192.168.1.200"
        
        guest.set_root_passwd("newpassword")
        assert guest.get_root_passwd() == "newpassword"

    def test_guest_tasks(self):
        """测试虚拟机任务管理"""
        guest = Guest(
            guest_id="test_guest",
            basevm_host="test_host",
            basevm_config_file="/path/to/vm.xml",
            basevm_os_type=OSType.UBUNTU,
            basevm_type=BaseVMType.KVM,
        )
        
        task = {"type": "install_package", "name": "nginx"}
        guest.add_task(task)
        
        tasks = guest.get_tasks()
        assert len(tasks) == 1
        assert tasks[0] == task

    def test_guest_config_file_validation(self):
        """测试配置文件路径验证"""
        # 有效的XML文件
        guest = Guest(
            guest_id="test_guest",
            basevm_host="test_host",
            basevm_config_file="/path/to/vm.xml",
            basevm_os_type=OSType.UBUNTU,
            basevm_type=BaseVMType.KVM,
        )
        assert guest.basevm_config_file == "/path/to/vm.xml"
        
        # 有效的JSON文件
        guest = Guest(
            guest_id="test_guest",
            basevm_host="test_host",
            basevm_config_file="/path/to/vm.json",
            basevm_os_type=OSType.UBUNTU,
            basevm_type=BaseVMType.KVM,
        )
        assert guest.basevm_config_file == "/path/to/vm.json"

    def test_guest_invalid_config_file(self):
        """测试无效配置文件路径"""
        with pytest.raises(ValueError, match="Config file must be .xml or .json"):
            Guest(
                guest_id="test_guest",
                basevm_host="test_host",
                basevm_config_file="/path/to/vm.txt",
                basevm_os_type=OSType.UBUNTU,
                basevm_type=BaseVMType.KVM,
            )


class TestGuestBuilder:
    """测试虚拟机构建器"""

    def test_guest_builder(self):
        """测试虚拟机构建器"""
        guest = (GuestBuilder()
                .with_guest_id("test_guest")
                .with_basevm_addr("192.168.1.100")
                .with_root_passwd("password")
                .with_basevm_host("test_host")
                .with_basevm_config_file("/path/to/vm.xml")
                .with_basevm_os_type(OSType.UBUNTU)
                .with_basevm_type(BaseVMType.KVM)
                .with_basevm_name("test_vm")
                .with_task({"type": "install", "package": "nginx"})
                .build())
        
        assert guest.guest_id == "test_guest"
        assert guest.basevm_addr == "192.168.1.100"
        assert guest.basevm_os_type == OSType.UBUNTU
        assert guest.basevm_type == BaseVMType.KVM
        assert len(guest.tasks) == 1

    def test_guest_builder_missing_required_fields(self):
        """测试虚拟机构建器缺少必需字段"""
        builder = GuestBuilder().with_guest_id("test_guest")
        
        with pytest.raises(ValueError, match="Missing required fields"):
            builder.build()


class TestEnums:
    """测试枚举类型"""

    def test_base_vm_type_enum(self):
        """测试虚拟化平台类型枚举"""
        assert BaseVMType.KVM == "kvm"
        assert BaseVMType.AWS == "aws"
        assert BaseVMType.DOCKER == "docker"

    def test_os_type_enum(self):
        """测试操作系统类型枚举"""
        assert OSType.UBUNTU == "ubuntu"
        assert OSType.WINDOWS_7 == "windows.7"
        assert OSType.AMAZON_LINUX == "amazon_linux"