#!/usr/bin/env python3
"""
Simple YAML Validation Test

Tests the test-kvm-auto-ubuntu.yml configuration file without CyRIS dependencies.
"""

import sys
import yaml
from pathlib import Path


def test_yaml_syntax():
    """Test basic YAML syntax"""
    config_file = Path("test-kvm-auto-ubuntu.yml")
    
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_file}")
        return False
    
    print(f"📁 Testing configuration file: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        
        print("✅ YAML syntax is valid")
        return data
    
    except yaml.YAMLError as e:
        print(f"❌ YAML syntax error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False


def test_yaml_structure(data):
    """Test YAML structure for kvm-auto"""
    print("\\n📋 Validating YAML structure...")
    
    if not isinstance(data, list):
        print("❌ Expected list format for configuration")
        return False
    
    has_host_settings = False
    has_guest_settings = False
    has_clone_settings = False
    
    for section in data:
        if not isinstance(section, dict):
            continue
            
        if 'host_settings' in section:
            has_host_settings = True
            hosts = section['host_settings']
            print(f"✅ Found {len(hosts)} host(s)")
            
        if 'guest_settings' in section:
            has_guest_settings = True
            guests = section['guest_settings']
            print(f"✅ Found {len(guests)} guest(s)")
            
            # Check for kvm-auto guests
            kvm_auto_count = 0
            for guest in guests:
                if guest.get('basevm_type') == 'kvm-auto':
                    kvm_auto_count += 1
                    guest_id = guest.get('id', 'unknown')
                    image_name = guest.get('image_name', 'unknown')
                    print(f"  🤖 kvm-auto guest: {guest_id} (image: {image_name})")
            
            if kvm_auto_count > 0:
                print(f"✅ Found {kvm_auto_count} kvm-auto guest(s)")
            else:
                print("⚠️ No kvm-auto guests found")
                
        if 'clone_settings' in section:
            has_clone_settings = True
            clones = section['clone_settings']
            print(f"✅ Found {len(clones)} clone setting(s)")
            
            for clone in clones:
                range_id = clone.get('range_id', 'unknown')
                print(f"  📦 Range: {range_id}")
    
    # Check required sections
    missing_sections = []
    if not has_host_settings:
        missing_sections.append('host_settings')
    if not has_guest_settings:
        missing_sections.append('guest_settings')
    if not has_clone_settings:
        missing_sections.append('clone_settings')
    
    if missing_sections:
        print(f"⚠️ Missing sections: {', '.join(missing_sections)}")
    else:
        print("✅ All required sections found")
    
    return len(missing_sections) == 0


def test_kvm_auto_requirements(data):
    """Test kvm-auto specific requirements"""
    print("\\n🤖 Validating kvm-auto requirements...")
    
    kvm_auto_guests = []
    
    # Extract kvm-auto guests
    for section in data:
        if isinstance(section, dict) and 'guest_settings' in section:
            for guest in section['guest_settings']:
                if guest.get('basevm_type') == 'kvm-auto':
                    kvm_auto_guests.append(guest)
    
    if not kvm_auto_guests:
        print("⚠️ No kvm-auto guests found - skipping kvm-auto validation")
        return True
    
    print(f"🔍 Validating {len(kvm_auto_guests)} kvm-auto guest(s)...")
    
    required_fields = ['id', 'image_name', 'vcpus', 'memory', 'disk_size']
    all_valid = True
    
    for i, guest in enumerate(kvm_auto_guests, 1):
        guest_id = guest.get('id', f'guest-{i}')
        print(f"  📱 Guest {i}: {guest_id}")
        
        # Check required fields
        missing_fields = []
        for field in required_fields:
            if field not in guest:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"    ❌ Missing fields: {', '.join(missing_fields)}")
            all_valid = False
        else:
            # Show configuration
            image = guest.get('image_name', 'unknown')
            vcpus = guest.get('vcpus', 'unknown')  
            memory = guest.get('memory', 'unknown')
            disk = guest.get('disk_size', 'unknown')
            
            print(f"    ✅ Configuration: {image}, {vcpus} vCPU, {memory} MB, {disk} disk")
            
            # Check tasks
            tasks = guest.get('tasks', [])
            if tasks:
                print(f"    📝 Tasks: {len(tasks)} task group(s)")
            else:
                print(f"    📝 Tasks: None")
    
    return all_valid


def main():
    print("🧪 YAML Configuration Test")
    print("Testing test-kvm-auto-ubuntu.yml\\n")
    
    # Test 1: YAML syntax
    data = test_yaml_syntax()
    if not data:
        print("\\n❌ YAML validation failed")
        return 1
    
    # Test 2: Structure validation
    structure_valid = test_yaml_structure(data)
    
    # Test 3: kvm-auto specific validation
    kvm_auto_valid = test_kvm_auto_requirements(data)
    
    # Summary
    print("\\n" + "="*50)
    print("Validation Summary")
    print("="*50)
    
    print(f"YAML Syntax: {'✅ Valid' if data else '❌ Invalid'}")
    print(f"Structure: {'✅ Valid' if structure_valid else '❌ Invalid'}")
    print(f"kvm-auto: {'✅ Valid' if kvm_auto_valid else '❌ Invalid'}")
    
    if data and structure_valid and kvm_auto_valid:
        print("\\n🎉 Configuration file is valid for kvm-auto workflow!")
        return 0
    else:
        print("\\n⚠️ Configuration file has issues that need to be addressed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())