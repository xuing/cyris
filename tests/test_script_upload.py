#!/usr/bin/env python3
"""
Test script upload and execution
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cyris.services.task_executor import TaskExecutor
from cyris.core.security import sanitize_for_shell

def test_script_upload():
    """Test script upload process"""
    config = {
        'base_path': '/home/ubuntu/cyris',
        'ssh_timeout': 30,
        'ssh_retries': 3
    }
    
    executor = TaskExecutor(config)
    
    username = "testuser"
    temp_script = f"/tmp/add_user_{username}_{os.getpid()}.sh"
    
    script_content = f"""#!/bin/bash
set -euo pipefail

# Create user
useradd -m -s /bin/bash "{sanitize_for_shell(username)}"

# Set password securely using chpasswd
echo "{sanitize_for_shell(username)}:$1" | chpasswd

echo "User {sanitize_for_shell(username)} created successfully"
"""
    
    print("🧪 Testing script upload process...")
    print(f"Script path: {temp_script}")
    print(f"Script content:\n{script_content}")
    
    # Test script upload
    upload_command = f"cat > {temp_script} << 'EOF'\n{script_content}\nEOF && chmod +x {temp_script}"
    print(f"\nUpload command: {upload_command[:100]}...")
    
    success, output, error = executor._execute_ssh_command(
        "192.168.122.47",
        upload_command
    )
    
    print(f"\nUpload result:")
    print(f"Success: {success}")
    print(f"Output: '{output.strip()}'")
    print(f"Error: '{error.strip()}'")
    
    if success:
        # Check if script exists and has execute permissions
        check_success, check_output, check_error = executor._execute_ssh_command(
            "192.168.122.47",
            f"ls -la {temp_script}"
        )
        
        print(f"\nScript check:")
        print(f"Success: {check_success}")
        print(f"Output: '{check_output.strip()}'")
        print(f"Error: '{check_error.strip()}'")
        
        # Try to execute a test version (just echo instead of useradd)
        test_success, test_output, test_error = executor._execute_ssh_command(
            "192.168.122.47",
            f"{temp_script} testpass123 'Test User'"
        )
        
        print(f"\nScript execution test:")
        print(f"Success: {test_success}")
        print(f"Output: '{test_output.strip()}'")
        print(f"Error: '{test_error.strip()}'")
        
        # Clean up
        executor._execute_ssh_command("192.168.122.47", f"rm -f {temp_script}")
    
    return success

if __name__ == "__main__":
    test_script_upload()