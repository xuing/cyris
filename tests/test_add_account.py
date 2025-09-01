#!/usr/bin/env python3
"""
Test the add_account task execution directly
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cyris.services.task_executor import TaskExecutor, TaskType

def test_add_account_task():
    """Test add_account task execution"""
    config = {
        'base_path': '/home/ubuntu/cyris',
        'ssh_timeout': 30,
        'ssh_retries': 3
    }
    
    executor = TaskExecutor(config)
    
    # Mock guest object
    class MockGuest:
        def __init__(self):
            self.basevm_os_type = 'linux'
            self.basevm_type = 'kvm'
    
    guest = MockGuest()
    
    # Test add account task
    import time
    unique_suffix = int(time.time()) % 10000
    username = f'testuser{unique_suffix}'
    params = {
        'account': username,
        'passwd': 'testpass123',
        'full_name': 'Test User'
    }
    
    print("🧪 Testing add_account task execution...")
    print(f"Connecting to VM: 192.168.122.47")
    print(f"Creating user: {params['account']}")
    
    start_time = time.time()
    
    try:
        result = executor._execute_add_account(
            task_id="test_add_account",
            params=params,
            guest_ip="192.168.122.47",
            guest=guest,
            start_time=start_time
        )
        
        print(f"\n📊 Task Result:")
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Output: {result.output}")
        print(f"Error: {result.error}")
        print(f"Execution time: {result.execution_time:.2f}s")
        
        return result.success
        
    except Exception as e:
        print(f"❌ Exception during task execution: {e}")
        return False

def test_ssh_command_directly():
    """Test SSH command execution directly"""
    config = {
        'base_path': '/home/ubuntu/cyris',
        'ssh_timeout': 30,
        'ssh_retries': 3
    }
    
    executor = TaskExecutor(config)
    
    print("\n🧪 Testing direct SSH command execution...")
    
    # Test basic SSH command
    success, output, error = executor._execute_ssh_command(
        "192.168.122.47",
        "whoami"
    )
    
    print(f"Basic SSH test:")
    print(f"Success: {success}")
    print(f"Output: '{output.strip()}'")
    print(f"Error: '{error.strip()}'")
    
    # Test sudo command
    success2, output2, error2 = executor._execute_ssh_command(
        "192.168.122.47",
        "sudo whoami"
    )
    
    print(f"\nSudo SSH test:")
    print(f"Success: {success2}")
    print(f"Output: '{output2.strip()}'")
    print(f"Error: '{error2.strip()}'")
    
    return success and success2

if __name__ == "__main__":
    print("🚀 Testing Add Account Task Execution")
    print("=" * 50)
    
    # First test basic SSH connectivity
    if test_ssh_command_directly():
        print("✅ SSH connectivity working")
        
        # Then test add_account task
        if test_add_account_task():
            print("✅ Add account task successful")
        else:
            print("❌ Add account task failed")
    else:
        print("❌ SSH connectivity failed")