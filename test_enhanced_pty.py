#!/usr/bin/env python3
"""
Test script for enhanced bidirectional PTY functionality
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.core.streaming_executor import StreamingCommandExecutor
from cyris.core.rich_progress import RichProgressManager

def test_basic_command():
    """Test basic command execution with PTY"""
    print("=== Test 1: Basic Command (ls -la) ===")
    
    progress_manager = RichProgressManager("test_command")
    executor = StreamingCommandExecutor(progress_manager=progress_manager)
    
    try:
        result = executor.execute_with_realtime_output(
            cmd=['ls', '-la', '/home/ubuntu/cyris'],
            description="Testing basic command",
            timeout=10,
            use_pty=True,
            allow_password_prompt=False
        )
        
        print(f"✅ Result: return code {result.returncode}")
        print(f"✅ Execution time: {result.execution_time:.2f}s")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_sudo_command():
    """Test sudo command with enhanced PTY"""
    print("\n=== Test 2: Sudo Command (sudo whoami) ===")
    print("🔐 This test will prompt for your password if needed")
    
    progress_manager = RichProgressManager("test_command")
    executor = StreamingCommandExecutor(progress_manager=progress_manager)
    
    try:
        result = executor.execute_with_realtime_output(
            cmd=['sudo', 'whoami'],
            description="Testing sudo with enhanced PTY",
            timeout=30,
            use_pty=True,
            allow_password_prompt=True
        )
        
        print(f"✅ Result: return code {result.returncode}")
        print(f"✅ Execution time: {result.execution_time:.2f}s")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_virt_builder_help():
    """Test virt-builder help command"""
    print("\n=== Test 3: Virt-builder Help ===")
    
    progress_manager = RichProgressManager("test_command")
    executor = StreamingCommandExecutor(progress_manager=progress_manager)
    
    try:
        result = executor.execute_with_realtime_output(
            cmd=['sudo', 'virt-builder', '--help'],
            description="Testing virt-builder help with enhanced PTY",
            timeout=30,
            use_pty=True,
            allow_password_prompt=True
        )
        
        print(f"✅ Result: return code {result.returncode}")
        print(f"✅ Execution time: {result.execution_time:.2f}s")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Enhanced PTY Functionality Test")
    print("=" * 50)
    
    tests = [
        ("Basic Command", test_basic_command),
        ("Sudo Command", test_sudo_command), 
        ("Virt-builder Help", test_virt_builder_help)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except KeyboardInterrupt:
            print(f"\n⚠️ Test interrupted by user")
            break
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced PTY is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)