#!/usr/bin/env python3
"""
Test script for the enhanced sudo workflow with PTY support
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.core.sudo_manager import SudoPermissionManager
from cyris.core.rich_progress import RichProgressManager

def test_sudo_authentication():
    """Test the enhanced sudo authentication with PTY"""
    print("🧪 Testing Enhanced Sudo Workflow with PTY")
    print("=" * 50)
    
    # Create a progress manager
    progress_manager = RichProgressManager("sudo_test")
    
    # Create sudo manager
    sudo_manager = SudoPermissionManager(progress_manager=progress_manager)
    
    print("\n1. 🔍 Checking current sudo status...")
    has_sudo = sudo_manager.check_sudo_status()
    print(f"   Current sudo status: {'✅ Available' if has_sudo else '❌ Not available'}")
    
    if has_sudo:
        has_access, remaining_time = sudo_manager.get_sudo_cache_info()
        if remaining_time:
            print(f"   Estimated remaining time: ≈{remaining_time} minutes")
    
    print("\n2. 🔐 Ensuring sudo access for virt-builder tools...")
    
    # This should use the enhanced PTY for password prompting if needed
    success = sudo_manager.ensure_sudo_access(
        operation="virt-builder tools verification",
        required_commands=['virt-builder', 'virt-install', 'virt-customize']
    )
    
    if success:
        print("\n✅ Sudo authentication successful!")
        print("\n3. 🧪 Testing virt-builder access...")
        
        # Test if we can actually run virt-builder now
        virt_builder_access = sudo_manager.validate_virt_builder_access()
        if virt_builder_access:
            print("✅ virt-builder access confirmed!")
            print("\n🎉 Enhanced sudo workflow test: PASSED")
            return True
        else:
            print("❌ virt-builder access failed")
            print("\n⚠️  Enhanced sudo workflow test: PARTIAL SUCCESS")
            return False
    else:
        print("\n❌ Sudo authentication failed")
        print("\n❌ Enhanced sudo workflow test: FAILED")
        return False

if __name__ == "__main__":
    success = test_sudo_authentication()
    sys.exit(0 if success else 1)