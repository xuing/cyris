#!/usr/bin/env python3
"""
简单的测试验证脚本，不依赖外部测试框架
"""
import sys
import os
import traceback
from pathlib import Path

# 添加main目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

def test_parse_config():
    """测试配置解析功能"""
    from parse_config import parse_config
    
    # 创建临时配置文件
    config_content = """[config]
cyris_path = /tmp/cyris/
cyber_range_dir = /tmp/cyris/cyber_range/
gw_mode = off
"""
    
    with open('/tmp/test_config.ini', 'w') as f:
        f.write(config_content)
    
    try:
        result = parse_config('/tmp/test_config.ini')
        # parse_config返回元组 (abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email)
        assert result is not None
        assert len(result) == 7
        abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email = result
        assert abs_path == '/tmp/cyris/'
        assert cr_dir == '/tmp/cyris/cyber_range/'
        assert gw_mode == False  # 'off' -> False
        print("✓ test_parse_config 通过")
        return True
    except Exception as e:
        print(f"✗ test_parse_config 失败: {e}")
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        if os.path.exists('/tmp/test_config.ini'):
            os.remove('/tmp/test_config.ini')

def test_entities():
    """测试实体类"""
    try:
        from entities import Host, Guest, Command
        
        # 测试Host创建 - 注意参数顺序: host_id, virbr_addr, mgmt_addr, account
        host = Host("test_host", "192.168.122.1", "192.168.1.1", "cyuser")
        assert host.host_id == "test_host"
        assert host.mgmt_addr == "192.168.1.1"
        assert host.virbr_addr == "192.168.122.1"
        assert host.account == "cyuser"
        
        # 测试Guest创建 - 需要所有必需参数
        # Guest(guest_id, basevm_addr, root_passwd, basevm_host, basevm_config_file, basevm_os_type, basevm_type, basevm_name, tasks)
        guest = Guest("test_guest", "192.168.1.100", "password", "test_host", "/path/to/vm.xml", "ubuntu", "kvm", "test_vm", [])
        assert guest.guest_id == "test_guest"
        assert guest.basevm_type == "kvm"
        assert guest.basevm_host == "test_host"
        
        # 测试Command创建
        cmd = Command("ls -la", "List files")
        assert cmd.command == "ls -la"
        assert cmd.description == "List files"
        
        print("✓ test_entities 通过")
        return True
    except Exception as e:
        print(f"✗ test_entities 失败: {e}")
        traceback.print_exc()
        return False

def test_modules():
    """测试功能模块"""
    try:
        from modules import Modules, SSHKeygenHostname, ManageUsers
        
        # 测试基础模块
        base_module = Modules("TestModule", "/tmp/cyris/")
        assert base_module.getName() == "TestModule"
        assert base_module.getAbsPath() == "/tmp/cyris/"
        
        # 测试SSH模块
        ssh_module = SSHKeygenHostname(
            "192.168.1.100", "password", "test-host", 
            "cyuser", "/tmp/cyris/", "ubuntu"
        )
        command = ssh_module.command()
        assert command is not None
        assert hasattr(command, 'command')
        
        # 测试用户管理模块
        user_mgr = ManageUsers("192.168.1.100", "/tmp/cyris/")
        assert user_mgr.addr == "192.168.1.100"
        
        print("✓ test_modules 通过")
        return True
    except Exception as e:
        print(f"✗ test_modules 失败: {e}")
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("CyRIS 基础功能测试")
    print("=" * 40)
    
    tests = [
        test_parse_config,
        test_entities,
        test_modules
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        if test_func():
            passed += 1
        print()
    
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有基础测试通过!")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())