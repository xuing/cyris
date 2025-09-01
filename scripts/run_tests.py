#!/usr/bin/env python3
"""
CyRIS 测试运行器
在没有Poetry的环境中运行测试的简化脚本
"""
import sys
import os
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def install_test_dependencies():
    """安装测试依赖"""
    deps = [
        'pytest>=7.0.0',
        'pytest-cov>=4.0.0', 
        'pytest-mock>=3.10.0'
    ]
    
    for dep in deps:
        try:
            print(f"正在安装 {dep}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], 
                         check=True, capture_output=True)
            print(f"✓ {dep} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"✗ {dep} 安装失败: {e}")
            return False
    
    return True

def run_tests():
    """运行测试"""
    try:
        print("开始运行测试...")
        
        # 运行单元测试
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'tests/unit/',
            '-v',
            '--tb=short',
            '--color=yes'
        ], cwd=project_root)
        
        return result.returncode == 0
        
    except FileNotFoundError:
        print("错误：pytest未安装")
        return False
    except Exception as e:
        print(f"运行测试时出错：{e}")
        return False

def main():
    """主函数"""
    print("CyRIS 测试运行器")
    print("=" * 50)
    
    # 检查并安装依赖
    if not install_test_dependencies():
        print("依赖安装失败，退出")
        return 1
    
    # 运行测试
    if run_tests():
        print("\n✓ 所有测试通过!")
        return 0
    else:
        print("\n✗ 测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())