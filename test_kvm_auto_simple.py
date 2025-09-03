#!/usr/bin/env python3
"""
Simple kvm-auto test without pydantic dependency
Tests YAML parsing and image validation
"""

import subprocess
import yaml
import sys
from pathlib import Path

def test_yaml_parsing():
    """Test basic YAML parsing"""
    print("🧪 Testing YAML Parsing...")
    
    test_files = [
        'test-kvm-auto.yml',
        'test-kvm-auto-enhanced.yml'
    ]
    
    for test_file in test_files:
        if Path(test_file).exists():
            try:
                with open(test_file, 'r') as f:
                    data = yaml.safe_load(f)
                print(f"  ✅ {test_file} - Valid YAML")
            except Exception as e:
                print(f"  ❌ {test_file} - Error: {e}")
                return False
        else:
            print(f"  ❌ {test_file} - File not found")
            return False
    
    return True

def test_tools_available():
    """Test that required tools are available"""
    print("🔧 Testing Tool Availability...")
    
    tools = ['virt-builder', 'virt-install', 'virt-customize']
    all_available = True
    
    for tool in tools:
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, timeout=10)
            if result.returncode == 0:
                print(f"  ✅ {tool} - Available")
            else:
                print(f"  ❌ {tool} - Not working properly")
                all_available = False
        except (subprocess.SubprocessError, FileNotFoundError):
            print(f"  ❌ {tool} - Not found")
            all_available = False
    
    return all_available

def test_images_available():
    """Test that images are available"""
    print("🖼️  Testing Image Availability...")
    
    try:
        result = subprocess.run(['virt-builder', '--list'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print("  ❌ Failed to get image list")
            return False
        
        available_images = []
        for line in result.stdout.split('\\n'):
            if line.strip() and not line.startswith(' '):
                image_name = line.split()[0]
                if image_name and not image_name.startswith('-'):
                    available_images.append(image_name)
        
        test_images = ['opensuse-tumbleweed', 'centos-7.0', 'alma-8.5']
        all_available = True
        
        for image in test_images:
            if image in available_images:
                print(f"  ✅ {image} - Available")
            else:
                print(f"  ❌ {image} - Not available")
                all_available = False
        
        print(f"  📊 Total available images: {len(available_images)}")
        return all_available
        
    except Exception as e:
        print(f"  ❌ Error checking images: {e}")
        return False

def test_dry_run():
    """Test dry run execution"""
    print("🚀 Testing Dry Run Execution...")
    
    try:
        cyris_cmd = ['./cyris', 'create', 'test-kvm-auto.yml', '--dry-run']
        print(f"  Running: {' '.join(cyris_cmd)}")
        
        result = subprocess.run(cyris_cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("  ✅ Dry run successful")
            if "kvm-auto" in result.stdout:
                print("  ✅ kvm-auto processing detected")
            return True
        else:
            print(f"  ❌ Dry run failed (exit code: {result.returncode})")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return False
            
    except Exception as e:
        print(f"  ❌ Dry run error: {e}")
        return False

def main():
    print("🧪 Simple kvm-auto Test Suite")
    print("=" * 50)
    
    tests = [
        ("YAML Parsing", test_yaml_parsing),
        ("Tool Availability", test_tools_available), 
        ("Image Availability", test_images_available),
        ("Dry Run", test_dry_run)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print()
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
    
    print()
    print("=" * 50)
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Basic kvm-auto functionality is working.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())