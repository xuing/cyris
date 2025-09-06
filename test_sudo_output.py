#!/usr/bin/env python3
"""
独立测试脚本：测试sudo命令传递和输出显示
目标：1. 保证能sudo传递 2. 第三方工具的输出不会乱掉（只行刷新变成一行一行的）
"""

import subprocess
import sys
import os
import time
import select
import pty

def test_method_1_basic_subprocess():
    """方法1: 基本subprocess - 测试sudo传递"""
    print("=" * 60)
    print("🧪 方法1: 基本subprocess")
    print("=" * 60)
    
    try:
        # 简单的sudo命令测试
        cmd = ['sudo', 'echo', 'Hello from sudo']
        print(f"执行命令: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        print(f"返回码: {result.returncode}")
        print(f"输出: {result.stdout}")
        if result.stderr:
            print(f"错误: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ 方法1失败: {e}")
        return False

def test_method_2_pipe_realtime():
    """方法2: 管道模式实时输出"""
    print("\n" + "=" * 60)
    print("🧪 方法2: 管道模式实时输出")
    print("=" * 60)
    
    try:
        # 使用一个会产生持续输出的命令来测试
        cmd = ['sudo', 'bash', '-c', 'for i in {1..5}; do echo "Progress $i/5"; sleep 1; done']
        print(f"执行命令: {' '.join(cmd)}")
        print("预期: 应该看到每秒一行输出")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=None,
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )
        
        print("开始实时输出:")
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"  -> {line.strip()}")
                sys.stdout.flush()
        
        process.wait()
        print(f"完成，返回码: {process.returncode}")
        
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ 方法2失败: {e}")
        return False

def test_method_3_pty_simple():
    """方法3: 简化PTY模式"""
    print("\n" + "=" * 60)
    print("🧪 方法3: 简化PTY模式")
    print("=" * 60)
    
    try:
        cmd = ['sudo', 'bash', '-c', 'for i in {1..3}; do echo "PTY Progress $i/3"; sleep 1; done']
        print(f"执行命令: {' '.join(cmd)}")
        
        master, slave = pty.openpty()
        
        process = subprocess.Popen(
            cmd,
            stdout=slave,
            stderr=slave, 
            stdin=slave,
            start_new_session=True
        )
        
        os.close(slave)
        
        print("PTY输出:")
        output_lines = []
        while process.poll() is None:
            try:
                ready, _, _ = select.select([master], [], [], 1.0)
                if master in ready:
                    data = os.read(master, 1024)
                    if data:
                        decoded = data.decode('utf-8', errors='replace')
                        sys.stdout.write(decoded)
                        sys.stdout.flush()
                        output_lines.append(decoded)
            except OSError:
                break
        
        # 读取剩余输出
        try:
            data = os.read(master, 1024)
            if data:
                decoded = data.decode('utf-8', errors='replace')
                sys.stdout.write(decoded)
                sys.stdout.flush()
        except OSError:
            pass
        
        process.wait()
        os.close(master)
        
        print(f"\n完成，返回码: {process.returncode}")
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ 方法3失败: {e}")
        return False

def test_method_4_virt_builder_simulation():
    """方法4: 模拟virt-builder命令"""
    print("\n" + "=" * 60)
    print("🧪 方法4: 模拟virt-builder命令")
    print("=" * 60)
    
    try:
        # 使用sudo --help来模拟virt-builder的输出（安全且快速）
        cmd = ['sudo', 'virt-builder', '--help']
        print(f"执行命令: {' '.join(cmd)}")
        print("这应该显示virt-builder的帮助信息")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=None,
            text=True,
            bufsize=1
        )
        
        print("输出:")
        line_count = 0
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"  {line.rstrip()}")
                sys.stdout.flush()
                line_count += 1
                if line_count > 10:  # 只显示前10行，避免输出过多
                    print("  ... (省略更多输出)")
                    break
        
        process.wait()
        print(f"\n返回码: {process.returncode}")
        
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ 方法4失败: {e}")
        return False

def main():
    print("🔧 Sudo命令传递和输出显示测试")
    print("目标: 1. 保证sudo传递 2. 输出不会变成一行一行的")
    print("")
    
    # 先检查sudo状态
    print("🔍 检查当前sudo状态:")
    try:
        result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=3)
        if result.returncode == 0:
            print("✅ sudo已缓存，无需密码")
        else:
            print("⚠️  sudo需要密码，测试可能需要输入密码")
    except:
        print("⚠️  无法检查sudo状态")
    print("")
    
    tests = [
        ("基本subprocess", test_method_1_basic_subprocess),
        ("管道模式实时输出", test_method_2_pipe_realtime), 
        ("简化PTY模式", test_method_3_pty_simple),
        ("virt-builder命令模拟", test_method_4_virt_builder_simulation)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔍 测试: {test_name}")
        try:
            success = test_func()
            results[test_name] = success
            print(f"{'✅' if success else '❌'} {test_name}: {'成功' if success else '失败'}")
        except KeyboardInterrupt:
            print(f"⚠️ {test_name}: 用户中断")
            results[test_name] = False
            break
        except Exception as e:
            print(f"❌ {test_name}: 异常 - {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    print("=" * 60)
    
    for test_name, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n总计: {success_count}/{total_count} 个测试通过")
    
    if success_count > 0:
        print("\n💡 建议:")
        for test_name, success in results.items():
            if success:
                print(f"  ✅ {test_name} 可以作为最终方案")
    else:
        print("\n⚠️ 所有测试都失败了，需要进一步调试")
    
    return success_count > 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n用户中断测试")
        sys.exit(1)