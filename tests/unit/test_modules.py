"""
测试功能模块
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch

# 添加main目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../main'))

from modules import (
    Modules, SSHKeygenHostname, ManageUsers, 
    InstallTools, EmulateAttacks
)


class TestModulesBase:
    """基础模块类测试"""

    def test_modules_creation(self):
        """测试模块基类创建"""
        module = Modules("TestModule", "/tmp/cyris/")
        
        assert module.getName() == "TestModule"
        assert module.getAbsPath() == "/tmp/cyris/"


class TestSSHKeygenHostname:
    """SSH密钥生成和主机名设置测试"""

    def test_ssh_keygen_creation(self):
        """测试SSH密钥生成模块创建"""
        ssh_module = SSHKeygenHostname(
            vm_addr="192.168.1.100",
            root_passwd="password",
            hostname="test-host",
            mstnode_account="cyuser",
            abspath="/tmp/cyris/",
            os_type="ubuntu"
        )
        
        assert ssh_module.vm_addr == "192.168.1.100"
        assert ssh_module.hostname == "test-host"
        assert ssh_module.os_type == "ubuntu"

    def test_ssh_keygen_command_linux(self):
        """测试Linux系统的SSH密钥生成命令"""
        ssh_module = SSHKeygenHostname(
            vm_addr="192.168.1.100",
            root_passwd="password", 
            hostname="test-host",
            mstnode_account="cyuser",
            abspath="/tmp/cyris/",
            os_type="ubuntu"
        )
        
        command = ssh_module.command()
        
        assert command is not None
        assert hasattr(command, 'command')
        assert hasattr(command, 'description')
        assert "sshkey_setup.sh" in command.command
        assert "hostname_setup.sh" in command.command

    def test_ssh_keygen_command_windows7(self):
        """测试Windows 7系统的SSH密钥生成命令"""
        ssh_module = SSHKeygenHostname(
            vm_addr="192.168.1.100",
            root_passwd="password",
            hostname="test-host", 
            mstnode_account="cyuser",
            abspath="/tmp/cyris/",
            os_type="windows.7"
        )
        
        command = ssh_module.command()
        
        assert command is not None
        assert "sshkey_setup_win_cmd.sh" in command.command


class TestManageUsers:
    """用户管理测试"""

    def test_manage_users_creation(self):
        """测试用户管理模块创建"""
        user_mgr = ManageUsers("192.168.1.100", "/tmp/cyris/")
        
        assert user_mgr.addr == "192.168.1.100"

    def test_add_account_linux_kvm(self):
        """测试在Linux KVM中添加账户"""
        user_mgr = ManageUsers("192.168.1.100", "/tmp/cyris/")
        
        command = user_mgr.add_account(
            new_account="testuser",
            new_passwd="testpass",
            full_name="Test User",
            os_type="ubuntu",
            basevm_type="kvm"
        )
        
        assert command is not None
        assert "add_user.sh" in command.command
        assert "testuser" in command.command
        assert "testpass" in command.command

    def test_add_account_windows7_kvm(self):
        """测试在Windows 7 KVM中添加账户"""
        user_mgr = ManageUsers("192.168.1.100", "/tmp/cyris/")
        
        command = user_mgr.add_account(
            new_account="testuser",
            new_passwd="testpass", 
            full_name="Test User",
            os_type="windows.7",
            basevm_type="kvm"
        )
        
        assert command is not None
        assert "net user" in command.command
        assert "testuser" in command.command

    def test_modify_account_password_only(self):
        """测试仅修改账户密码"""
        user_mgr = ManageUsers("192.168.1.100", "/tmp/cyris/")
        
        command = user_mgr.modify_account(
            account="olduser",
            new_account="null",
            new_passwd="newpass",
            os_type="ubuntu",
            basevm_type="kvm"
        )
        
        assert command is not None
        assert "modify_user.sh" in command.command
        assert "new password: newpass" in command.description


class TestInstallTools:
    """工具安装测试"""

    def test_install_tools_creation(self):
        """测试工具安装模块创建"""
        tools = InstallTools("192.168.1.100", "cyuser", "/tmp/cyris/")
        
        assert tools.addr == "192.168.1.100"
        assert tools.account == "cyuser"

    def test_install_command(self):
        """测试安装命令生成"""
        tools = InstallTools("192.168.1.100", "cyuser", "/tmp/cyris/")
        
        command = tools.package_install_command("apt", "vim", "", "ubuntu", "kvm")
        
        assert command is not None
        assert hasattr(command, 'command')
        assert hasattr(command, 'description')


class TestEmulateAttacks:
    """攻击模拟测试"""

    def test_emulate_attacks_creation(self):
        """测试攻击模拟模块创建"""
        attacks = EmulateAttacks("ssh_attack", "192.168.1.100", "target_user", 5, "10", "/tmp/cyris/", "kvm")
        
        assert attacks.target_addr == "192.168.1.100"
        assert attacks.attack_type == "ssh_attack"
        assert attacks.target_account == "target_user"
        assert attacks.number == 5
        assert attacks.attack_time == "10"
        assert attacks.basevm_type == "kvm"

    def test_attack_command_generation(self):
        """测试攻击命令生成"""
        attacks = EmulateAttacks("ssh_attack", "192.168.1.100", "target_user", 5, "10", "/tmp/cyris/", "kvm")
        
        command = attacks.command()
        
        assert command is not None
        assert hasattr(command, 'command')
        assert hasattr(command, 'description')
        assert "ssh_attack" in command.description or "ssh attack" in command.description