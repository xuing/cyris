#!/usr/bin/env python3
"""
真实的virt-builder测试脚本 - 增强版
目标：测试完整的sudo virt-builder命令，同时解决：
1. sudo传递问题
2. 进度条显示问题（一行一行 → 同行刷新）
"""

import subprocess
import sys
import os
import time
import getpass
import pty
import select
from pathlib import Path

def setup_test_environment():
    """设置测试环境"""
    print("🔧 设置测试环境")
    
    # 创建输出目录
    output_dir = Path("/home/ubuntu/cyris/images/builds")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建输出目录: {output_dir}")
    
    # 输出文件路径
    output_file = output_dir / "debian-server-debian-11.qcow2"
    
    # 如果文件已存在，删除它
    if output_file.exists():
        try:
            output_file.unlink()
            print(f"✅ 删除已存在的文件: {output_file}")
        except Exception as e:
            print(f"⚠️ 无法删除已存在文件: {e}")
    
    return str(output_file)

def check_sudo_status():
    """检查sudo状态"""
    print("\n🔍 检查sudo状态:")
    
    try:
        result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=3)
        if result.returncode == 0:
            print("✅ sudo已缓存，无需密码")
            return True
        else:
            print("⚠️ sudo需要密码")
            return False
    except Exception as e:
        print(f"⚠️ 无法检查sudo状态: {e}")
        return False

def clear_sudo_cache():
    """清除sudo缓存来测试密码输入"""
    print("\n🧹 清除sudo缓存(模拟需要密码的情况)")
    try:
        subprocess.run(['sudo', '-k'], check=True)
        print("✅ sudo缓存已清除")
        return True
    except Exception as e:
        print(f"❌ 清除sudo缓存失败: {e}")
        return False

def universal_output_processor(data):
    """通用输出处理器：基于\\r字符检测，适用于所有进度条工具"""
    if not data:
        return
    
    # 检测是否包含回车符 - 这是进度条的通用标准
    if '\r' in data:
        # 包含\r的数据 - 按\r分割处理
        parts = data.split('\r')
        for i, part in enumerate(parts):
            part = part.rstrip('\n')  # 移除可能的换行符
            if not part:  # 空内容跳过
                continue
                
            if i == len(parts) - 1:
                # 最后一部分
                if part:
                    if data.endswith('\n'):
                        print(f"\r  {part}")  # 完成后换行
                        universal_output_processor._last_was_overwrite = False
                    else:
                        print(f"\r  {part}", end='', flush=True)  # 覆盖显示
                        universal_output_processor._last_was_overwrite = True
            else:
                # 中间部分 - 都是覆盖显示
                if part:
                    print(f"\r  {part}", end='', flush=True)
                    universal_output_processor._last_was_overwrite = True
    else:
        # 不包含\r的普通输出
        data = data.rstrip()
        if data:
            # 如果前面有覆盖输出，先换行
            if hasattr(universal_output_processor, '_last_was_overwrite'):
                if universal_output_processor._last_was_overwrite:
                    print()  # 换行结束覆盖输出
            print(f"  {data}")
            universal_output_processor._last_was_overwrite = False

def test_method_single_pty_session(output_file):
    """方法A: 单一PTY会话 (sudo认证 + 命令执行在同一PTY)"""
    print("\n" + "=" * 80)
    print("🧪 方法A: 单一PTY会话 (终极解决方案)")
    print("=" * 80)
    
    cmd = [
        'sudo', 'virt-builder', 'debian-11', 
        '--size', '8G',
        '--format', 'qcow2', 
        '--output', output_file
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print("预期: PTY模式 + 同一会话sudo认证 = 完美进度条显示")
    print("\n开始执行:")
    
    try:
        # 创建PTY
        master, slave = pty.openpty()
        
        # 设置环境变量
        env = os.environ.copy()
        env.update({
            'TERM': 'xterm-256color',
            'COLUMNS': '120',
            'LINES': '30'
        })
        
        # 在PTY中启动bash会话
        process = subprocess.Popen(
            ['bash', '-c', f'exec {" ".join(cmd)}'],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            preexec_fn=os.setsid  # 创建新会话
        )
        
        os.close(slave)  # 关闭子进程端
        
        # 实时读取PTY输出
        output_buffer = []
        start_time = time.time()
        
        while process.poll() is None:
            # 检查是否有数据可读 (超时1秒)
            ready, _, _ = select.select([master], [], [], 1.0)
            
            if master in ready:
                try:
                    data = os.read(master, 1024)
                    if data:
                        decoded = data.decode('utf-8', errors='replace')
                        
                        # 检查是否是sudo密码提示
                        if any(prompt in decoded.lower() for prompt in ['password', '[sudo]', 'sorry']):
                            print(f"\n🔐 检测到sudo密码提示")
                            # 获取密码并发送
                            try:
                                password = getpass.getpass("请输入sudo密码: ")
                                os.write(master, (password + '\n').encode())
                                print("密码已发送，继续执行...")
                            except (KeyboardInterrupt, EOFError):
                                print("\n密码输入取消")
                                break
                        else:
                            # 正常输出 - 直接显示 (PTY会处理\r字符)
                            sys.stdout.write(decoded)
                            sys.stdout.flush()
                            output_buffer.append(decoded)
                            
                except OSError as e:
                    if e.errno == 5:  # Input/output error - PTY关闭
                        break
                    else:
                        print(f"读取PTY时出错: {e}")
            
            # 检查超时 (10分钟)
            if time.time() - start_time > 600:
                print("\n⏰ 命令执行超时")
                break
        
        # 读取剩余输出
        try:
            while True:
                ready, _, _ = select.select([master], [], [], 0.1)
                if not ready:
                    break
                data = os.read(master, 1024)
                if not data:
                    break
                decoded = data.decode('utf-8', errors='replace')
                sys.stdout.write(decoded)
                sys.stdout.flush()
                output_buffer.append(decoded)
        except OSError:
            pass
        
        # 等待进程结束
        process.wait()
        os.close(master)
        
        print(f"\n\n完成，返回码: {process.returncode}")
        execution_time = time.time() - start_time
        print(f"执行时间: {execution_time:.1f}秒")
        
        # 检查输出文件
        if process.returncode == 0:
            if Path(output_file).exists():
                file_size = Path(output_file).stat().st_size / (1024*1024*1024)  # GB
                print(f"✅ 输出文件已创建: {output_file}")
                print(f"   文件大小: {file_size:.2f} GB")
            else:
                print("⚠️ 命令成功但文件不存在")
        
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ PTY会话执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_method_universal_pipe(output_file):
    """方法A: 管道模式 + 通用\\r字符检测"""
    print("\n" + "=" * 80)
    print("🧪 方法A: 管道模式 + 通用\\r检测 (适用于所有工具)")
    print("=" * 80)
    
    # 确保有sudo缓存
    print("确保sudo缓存可用...")
    try:
        result = subprocess.run(['sudo', '-v'], timeout=30)
        if result.returncode != 0:
            print("❌ sudo认证失败")
            return False
    except Exception as e:
        print(f"❌ sudo认证异常: {e}")
        return False
    
    cmd = [
        'sudo', 'virt-builder', 'debian-11', 
        '--size', '8G',
        '--format', 'qcow2', 
        '--output', output_file
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print("预期: 通用\\r检测实现进度条覆盖显示")
    print("\n开始执行:")
    
    # 重置通用处理器状态
    universal_output_processor._last_was_overwrite = False
    
    try:
        # 设置环境变量帮助工具识别终端
        env = os.environ.copy()
        env.update({
            'TERM': 'xterm-256color',
            'COLUMNS': '120',
            'LINES': '30'
        })
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并stderr到stdout
            stdin=None,
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True,
            env=env
        )
        
        output_lines = []
        line_count = 0
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line_count += 1
                universal_output_processor(line)
                output_lines.append(line.rstrip())
        
        # 确保最后换行
        if hasattr(universal_output_processor, '_last_was_overwrite'):
            if universal_output_processor._last_was_overwrite:
                print()
        
        process.wait()
        
        print(f"\n完成，返回码: {process.returncode}")
        print(f"总输出行数: {line_count}")
        
        # 检查输出文件
        if process.returncode == 0:
            if Path(output_file).exists():
                file_size = Path(output_file).stat().st_size / (1024*1024*1024)  # GB
                print(f"✅ 输出文件已创建: {output_file}")
                print(f"   文件大小: {file_size:.2f} GB")
            else:
                print("⚠️ 命令成功但文件不存在")
        
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return False

def test_method_original_pipe(output_file):
    """方法B: 原始管道模式 (对比测试)"""
    print("\n" + "=" * 80)
    print("🧪 方法B: 原始管道模式 (对比：一行一行输出)")
    print("=" * 80)
    
    # 确保有sudo缓存
    print("确保sudo缓存可用...")
    try:
        result = subprocess.run(['sudo', '-v'], timeout=30)
        if result.returncode != 0:
            print("❌ sudo认证失败")
            return False
    except Exception as e:
        print(f"❌ sudo认证异常: {e}")
        return False
    
    cmd = [
        'sudo', 'virt-builder', 'debian-11', 
        '--size', '8G',
        '--format', 'qcow2', 
        '--output', output_file + '.original'
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print("预期: 一行一行输出 (原始行为)")
    print("\n开始执行:")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并stderr到stdout
            stdin=None,
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )
        
        output_lines = []
        line_count = 0
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line_count += 1
                # 原始输出方式：每行直接打印
                print(f"  {line.rstrip()}")
                sys.stdout.flush()
                output_lines.append(line.rstrip())
        
        process.wait()
        
        print(f"\n完成，返回码: {process.returncode}")
        print(f"总输出行数: {line_count}")
        
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return False

def test_method_pipe_with_password(output_file):
    """方法C: 管道模式 + sudo -S 密码输入"""
    print("\n" + "=" * 80)
    print("🧪 方法C: 管道模式 + sudo -S 密码输入")
    print("=" * 80)
    
    # 清除sudo缓存
    clear_sudo_cache()
    
    # 获取密码
    print("需要输入sudo密码以继续测试...")
    try:
        password = getpass.getpass("🔐 请输入sudo密码: ")
        if not password:
            print("❌ 未输入密码")
            return False
    except (KeyboardInterrupt, EOFError):
        print("\n❌ 密码输入取消")
        return False
    
    cmd = [
        'sudo', '-S',  # 从stdin读取密码
        'virt-builder', 'debian-11', 
        '--size', '8G',
        '--format', 'qcow2', 
        '--output', output_file + '.method_b'  # 不同的文件名
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print("预期: 使用密码认证后显示实时进度")
    print("\n开始执行:")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 发送密码
        process.stdin.write(password + '\n')
        process.stdin.flush()
        process.stdin.close()
        
        # 清除内存中的密码
        password = None
        
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"  {line.rstrip()}")
                sys.stdout.flush()
                output_lines.append(line.rstrip())
        
        process.wait()
        
        print(f"\n完成，返回码: {process.returncode}")
        
        return process.returncode == 0
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return False

def test_method_simple_subprocess(output_file):
    """方法C: 简单subprocess（作为对比）"""
    print("\n" + "=" * 80)
    print("🧪 方法C: 简单subprocess（对比测试）")
    print("=" * 80)
    
    # 确保有sudo缓存
    print("确保sudo缓存可用...")
    try:
        result = subprocess.run(['sudo', '-v'], timeout=30)
        if result.returncode != 0:
            print("❌ sudo认证失败")
            return False
    except Exception as e:
        print(f"❌ sudo认证异常: {e}")
        return False
    
    cmd = [
        'sudo', 'virt-builder', 'debian-11', 
        '--size', '8G',
        '--format', 'qcow2', 
        '--output', output_file + '.method_c'
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print("预期: 可能会看到缓冲的输出（不是实时的）")
    print("\n开始执行:")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        print("输出:")
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    print(f"  {line}")
        
        if result.stderr:
            print("错误输出:")
            for line in result.stderr.split('\n'):
                if line.strip():
                    print(f"  ERROR: {line}")
        
        print(f"\n完成，返回码: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ 命令超时")
        return False
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return False

def main():
    print("🔧 真实virt-builder命令测试 - 增强版")
    print("目标: 测试完整的sudo virt-builder命令，同时解决：")
    print("  1. ✅ sudo认证传递")
    print("  2. ✅ 进度条正确显示 (同行刷新而非一行一行)")
    print("⚠️  这将下载并构建真实的Debian 11镜像，可能需要几分钟时间")
    print("")
    
    # 询问用户是否继续
    try:
        confirm = input("是否继续？这将下载大约500MB的数据 [y/N]: ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("取消测试")
            return False
    except (KeyboardInterrupt, EOFError):
        print("\n取消测试")
        return False
    
    # 设置环境
    output_file = setup_test_environment()
    
    # 检查初始sudo状态
    initial_sudo = check_sudo_status()
    
    # 测试不同方法
    tests = [
        ("单一PTY会话", lambda: test_method_single_pty_session(output_file)),
        ("通用\\r检测管道模式", lambda: test_method_universal_pipe(output_file)),
        ("原始管道模式", lambda: test_method_original_pipe(output_file)),
        ("管道模式+密码输入", lambda: test_method_pipe_with_password(output_file)),
        ("简单subprocess", lambda: test_method_simple_subprocess(output_file))
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔍 开始测试: {test_name}")
        
        try:
            # 询问是否执行此测试
            confirm = input(f"执行 {test_name} 测试？ [Y/n]: ").strip().lower()
            if confirm in ['n', 'no']:
                print(f"⏭️  跳过 {test_name}")
                results[test_name] = None
                continue
            
            success = test_func()
            results[test_name] = success
            
            status = "✅ 成功" if success else "❌ 失败"
            print(f"\n{status} {test_name}")
            
            if success:
                print("💡 这种方法可以作为最终解决方案")
            
        except KeyboardInterrupt:
            print(f"\n⚠️ {test_name}: 用户中断")
            results[test_name] = False
            break
        except Exception as e:
            print(f"❌ {test_name}: 异常 - {e}")
            results[test_name] = False
    
    # 总结结果
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    
    for test_name, result in results.items():
        if result is None:
            status = "⏭️ 跳过"
        elif result:
            status = "✅ 成功"
        else:
            status = "❌ 失败"
        print(f"  {test_name}: {status}")
    
    # 推荐方案
    successful_methods = [name for name, result in results.items() if result is True]
    
    if successful_methods:
        print(f"\n💡 推荐使用的方法:")
        for method in successful_methods:
            print(f"  ✅ {method}")
        
        print(f"\n🚀 建议在cyris中使用最快且最稳定的方法来替换当前的PTY实现")
    else:
        print(f"\n⚠️ 没有方法完全成功，需要进一步调试")
    
    return len(successful_methods) > 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
        sys.exit(1)