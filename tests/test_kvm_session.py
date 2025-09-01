#!/usr/bin/env python3

"""
Test script to verify KVM provider works with user session
"""

import sys
import os
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.domain.entities.guest import Guest

def test_kvm_session_connection():
    """Test KVM provider connection with session URI"""
    print("Testing KVM provider with qemu:///session URI...")
    
    # Create provider config with session URI
    config = {
        "libvirt_uri": "qemu:///session",
        "base_path": "/tmp/cyris-test"
    }
    
    try:
        # Initialize KVM provider
        provider = KVMProvider(config)
        print(f"✓ KVM provider initialized successfully")
        print(f"  URI: {provider.libvirt_uri}")
        print(f"  Libvirt type: {provider.__class__.__module__}")
        
        # Test connection
        provider.connect()
        print("✓ Connection established successfully")
        
        # Test connection status
        is_connected = provider.is_connected()
        print(f"✓ Connection status: {is_connected}")
        
        # Test basic operations
        print("\nTesting basic operations...")
        
        # Create a test guest entity
        test_guest = Guest(
            guest_id="test-vm", 
            ip_addr="192.168.100.101", 
            password="testpass", 
            basevm_host="localhost",
            basevm_config_file="/home/ubuntu/cyris/images/basevm.xml",
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test-base-vm",
            tasks=[]
        )
        
        # Test guest creation (should work even in mock mode)
        guest_ids = provider.create_guests([test_guest], {"localhost": "local"})
        print(f"✓ Guest creation test completed: {guest_ids}")
        
        # Get status
        status = provider.get_status(guest_ids)
        print(f"✓ Status check: {status}")
        
        # Clean up
        if guest_ids:
            provider.destroy_guests(guest_ids)
            print("✓ Cleanup completed")
        
        provider.disconnect()
        print("✓ Disconnected successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_virsh_availability():
    """Test if virsh command is available"""
    print("\nTesting virsh command availability...")
    
    import subprocess
    try:
        result = subprocess.run(
            ["virsh", "--connect", "qemu:///session", "version"],
            capture_output=True, text=True, check=True
        )
        print("✓ virsh command available")
        print(f"  Version info: {result.stdout.strip().split(chr(10))[0]}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ virsh command failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("✗ virsh command not found")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("KVM Session Connection Test")
    print("=" * 50)
    
    virsh_available = test_virsh_availability()
    kvm_working = test_kvm_session_connection()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Virsh available: {'✓' if virsh_available else '✗'}")
    print(f"KVM provider working: {'✓' if kvm_working else '✗'}")
    
    if virsh_available and kvm_working:
        print("✓ Ready for real VM creation!")
    else:
        print("✗ Issues detected - check output above")