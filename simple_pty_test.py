#!/usr/bin/env python3
"""
Simple test for enhanced PTY functionality
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, '/home/ubuntu/cyris/src')

try:
    from cyris.core.streaming_executor import StreamingCommandExecutor
    print("✅ StreamingCommandExecutor imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_simple_command():
    """Test a simple command without progress manager"""
    print("\n=== Testing Simple Command ===")
    
    executor = StreamingCommandExecutor()
    
    try:
        print("🔄 Executing: echo 'Hello PTY World'")
        result = executor.execute_with_realtime_output(
            cmd=['echo', 'Hello PTY World'],
            description="Testing simple echo command",
            timeout=5,
            use_pty=True,
            allow_password_prompt=False
        )
        
        print(f"✅ Return code: {result.returncode}")
        print(f"✅ Execution time: {result.execution_time:.2f}s")
        print(f"✅ Output length: {len(result.stdout)} chars")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_sudo():
    """Test basic sudo command"""
    print("\n=== Testing Basic Sudo Command ===")
    print("🔐 This may prompt for your password")
    
    executor = StreamingCommandExecutor()
    
    try:
        print("🔄 Executing: sudo echo 'Sudo test'")
        result = executor.execute_with_realtime_output(
            cmd=['sudo', 'echo', 'Sudo test'],
            description="Testing basic sudo command",
            timeout=30,
            use_pty=True,
            allow_password_prompt=True
        )
        
        print(f"✅ Return code: {result.returncode}")
        print(f"✅ Execution time: {result.execution_time:.2f}s")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Simple PTY Test")
    print("=" * 40)
    
    # Test 1: Simple command
    if test_simple_command():
        print("\n✅ Simple command test: PASSED")
    else:
        print("\n❌ Simple command test: FAILED")
        sys.exit(1)
    
    # Test 2: Sudo command (interactive)
    print("\n" + "=" * 40)
    print("🔐 Interactive sudo test (requires password)")
    user_input = input("Continue with sudo test? [y/N]: ").strip().lower()
    
    if user_input in ['y', 'yes']:
        if test_basic_sudo():
            print("\n✅ Sudo command test: PASSED")
        else:
            print("\n❌ Sudo command test: FAILED")
    else:
        print("\n⏭️ Skipping sudo test")
    
    print("\n🎉 Test completed!")