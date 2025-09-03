#!/usr/bin/env python3
"""
Simple test script for kvm-auto validation without full dependencies
"""

import subprocess
import yaml
from pathlib import Path

def check_virt_tools():
    """Check availability of virt-builder tools"""
    tools = {}
    for tool in ['virt-builder', 'virt-install', 'virt-customize']:
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, timeout=10)
            tools[tool] = result.returncode == 0
            print(f"Tool {tool}: {'✅ available' if tools[tool] else '❌ not available'}")
        except (subprocess.SubprocessError, FileNotFoundError):
            tools[tool] = False
            print(f"Tool {tool}: ❌ not found")
    return tools

def validate_yaml_structure(yaml_path):
    """Validate YAML structure for kvm-auto"""
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        print(f"✅ YAML loaded successfully from {yaml_path}")
        
        # Find guest_settings
        guest_settings = None
        for section in data:
            if 'guest_settings' in section:
                guest_settings = section['guest_settings']
                break
        
        if not guest_settings:
            print("❌ No guest_settings found in YAML")
            return False
        
        kvm_auto_guests = []
        for guest in guest_settings:
            if guest.get('basevm_type') == 'kvm-auto':
                kvm_auto_guests.append(guest)
        
        if not kvm_auto_guests:
            print("ℹ️ No kvm-auto guests found in configuration")
            return True
        
        print(f"🔧 Found {len(kvm_auto_guests)} kvm-auto guests")
        
        # Validate each kvm-auto guest
        all_valid = True
        for guest in kvm_auto_guests:
            guest_id = guest.get('id', 'unknown')
            print(f"  Validating guest: {guest_id}")
            
            required_fields = ['image_name', 'vcpus', 'memory', 'disk_size']
            for field in required_fields:
                if field not in guest:
                    print(f"    ❌ Missing required field: {field}")
                    all_valid = False
                else:
                    print(f"    ✅ {field}: {guest[field]}")
            
            # Check tasks structure
            if 'tasks' in guest:
                print(f"    ✅ tasks: {len(guest['tasks'])} tasks found")
                for task in guest['tasks']:
                    if 'add_account' in task:
                        print(f"      - add_account with {len(task['add_account'])} accounts")
                    elif 'modify_account' in task:
                        print(f"      - modify_account with {len(task['modify_account'])} accounts")
        
        return all_valid
        
    except Exception as e:
        print(f"❌ Error validating YAML: {e}")
        return False

def show_installation_guide():
    """Show installation guide for missing tools"""
    print("\n📋 Installation Guide:")
    print("For Ubuntu/Debian:")
    print("  sudo apt update")
    print("  sudo apt install libguestfs-tools virtinst")
    print()
    print("For CentOS/RHEL:")
    print("  sudo yum install libguestfs-tools virt-install")
    print()
    print("🔧 Example kvm-auto configuration:")
    print("guest_settings:")
    print("  - id: ubuntu-desktop")
    print("    basevm_type: kvm-auto")
    print("    image_name: ubuntu-20.04")
    print("    vcpus: 2")
    print("    memory: 2048")
    print("    disk_size: 20G")
    print("    tasks:")
    print("    - add_account:")
    print("      - account: trainee")
    print("        passwd: training123")

def main():
    print("🧪 Testing kvm-auto functionality")
    print("=" * 50)
    
    print("\n1. Checking virt-tools availability:")
    tools = check_virt_tools()
    
    print("\n2. Validating YAML configuration:")
    yaml_valid = validate_yaml_structure('test-kvm-auto.yml')
    
    print("\n3. Summary:")
    if tools.get('virt-builder', False) and tools.get('virt-customize', False) and tools.get('virt-install', False):
        if yaml_valid:
            print("✅ All checks passed! kvm-auto is ready to use.")
        else:
            print("❌ YAML configuration has issues.")
    else:
        print("❌ Missing required tools for kvm-auto.")
        show_installation_guide()
    
    print("\n🎯 Testing complete!")

if __name__ == "__main__":
    main()