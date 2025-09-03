#!/usr/bin/env python3
"""
Comprehensive test suite for kvm-auto functionality
Tests parsing, validation, and VM creation workflow
"""

import subprocess
import yaml
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
import json

def print_header(title: str):
    """Print a formatted test section header"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_status(test_name: str, passed: bool, details: str = ""):
    """Print test status with formatting"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"     {details}")

def check_virt_tools() -> Dict[str, bool]:
    """Check availability of required virtualization tools"""
    print_header("Checking Virtualization Tools")
    
    tools = {}
    required_tools = ['virt-builder', 'virt-install', 'virt-customize', 'virsh', 'qemu-img']
    
    for tool in required_tools:
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, timeout=10)
            available = result.returncode == 0
            tools[tool] = available
            print_status(f"{tool} availability", available)
        except (subprocess.SubprocessError, FileNotFoundError):
            tools[tool] = False
            print_status(f"{tool} availability", False, "Command not found")
    
    return tools

def test_yaml_parsing() -> bool:
    """Test YAML configuration parsing for all test files"""
    print_header("Testing YAML Configuration Parsing")
    
    test_files = [
        'test-kvm-auto.yml',
        'test-kvm-auto-debian.yml', 
        'test-kvm-auto-multi.yml',
        'test-kvm-auto-advanced.yml',
        'test-kvm-auto-enhanced.yml'
    ]
    
    all_passed = True
    
    for test_file in test_files:
        if not Path(test_file).exists():
            print_status(f"Parse {test_file}", False, "File not found")
            all_passed = False
            continue
            
        try:
            with open(test_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Basic structure validation
            has_guests = False
            kvm_auto_count = 0
            
            if isinstance(data, list):
                for section in data:
                    if 'guest_settings' in section:
                        has_guests = True
                        for guest in section['guest_settings']:
                            if guest.get('basevm_type') == 'kvm-auto':
                                kvm_auto_count += 1
            
            success = has_guests and kvm_auto_count > 0
            details = f"{kvm_auto_count} kvm-auto guests found" if success else "No kvm-auto guests"
            print_status(f"Parse {test_file}", success, details)
            
            if not success:
                all_passed = False
                
        except Exception as e:
            print_status(f"Parse {test_file}", False, f"Error: {e}")
            all_passed = False
    
    return all_passed

def test_cyris_config_parsing() -> bool:
    """Test CyRIS configuration parsing with new fields"""
    print_header("Testing CyRIS Configuration Integration")
    
    try:
        # Add CyRIS to Python path
        sys.path.insert(0, '/home/ubuntu/cyris/src')
        
        from cyris.config.parser import CyRISConfigParser
        from cyris.domain.entities.guest import BaseVMType
        
        parser = CyRISConfigParser()
        
        test_cases = [
            ('test-kvm-auto-enhanced.yml', 'Enhanced configuration'),
            ('test-kvm-auto-multi.yml', 'Multi-VM configuration'),
        ]
        
        all_passed = True
        
        for test_file, description in test_cases:
            if not Path(test_file).exists():
                print_status(f"Parse {description}", False, "File not found")
                all_passed = False
                continue
                
            try:
                config = parser.parse_file(test_file)
                
                # Validate parsing results
                kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
                
                success = len(kvm_auto_guests) > 0
                details = f"{len(kvm_auto_guests)} kvm-auto guests parsed"
                
                # Additional validation for enhanced features
                if test_file == 'test-kvm-auto-enhanced.yml':
                    enhanced_features = 0
                    for guest in kvm_auto_guests:
                        if hasattr(guest, 'graphics_type') and guest.graphics_type:
                            enhanced_features += 1
                        if hasattr(guest, 'network_model') and guest.network_model:
                            enhanced_features += 1
                        if hasattr(guest, 'os_variant') and guest.os_variant:
                            enhanced_features += 1
                    
                    if enhanced_features > 0:
                        details += f", {enhanced_features} enhanced features"
                
                print_status(f"Parse {description}", success, details)
                
                if not success:
                    all_passed = False
                    
            except Exception as e:
                print_status(f"Parse {description}", False, f"Error: {e}")
                all_passed = False
        
        return all_passed
        
    except ImportError as e:
        print_status("CyRIS Import", False, f"Import error: {e}")
        return False

def test_image_validation() -> bool:
    """Test virt-builder image validation"""
    print_header("Testing Image Validation")
    
    try:
        # Get available images
        result = subprocess.run(['virt-builder', '--list'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print_status("Get image list", False, "virt-builder --list failed")
            return False
        
        available_images = []
        for line in result.stdout.split('\n'):
            if line.strip() and not line.startswith(' '):
                image_name = line.split()[0]
                if image_name and not image_name.startswith('-'):
                    available_images.append(image_name)
        
        print_status("Get image list", True, f"{len(available_images)} images available")
        
        # Test images used in configurations
        test_images = ['ubuntu-20.04', 'ubuntu-22.04', 'centos-stream-9', 'debian-11', 'fedora-38']
        
        all_passed = True
        for image in test_images:
            available = image in available_images
            print_status(f"Image {image}", available, 
                        "Available" if available else "Not available")
            if not available:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print_status("Image validation", False, f"Error: {e}")
        return False

def test_vm_creation_dry_run() -> bool:
    """Test VM creation in dry-run mode"""
    print_header("Testing VM Creation (Dry Run)")
    
    try:
        # Test with a simple configuration
        cyris_cmd = ['/home/ubuntu/cyris/cyris', 'create', 'test-kvm-auto.yml', '--dry-run']
        
        print(f"Running: {' '.join(cyris_cmd)}")
        result = subprocess.run(cyris_cmd, capture_output=True, text=True, timeout=120)
        
        success = result.returncode == 0
        details = "Dry run completed" if success else f"Exit code: {result.returncode}"
        
        print_status("Dry run execution", success, details)
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
            
        if result.stderr and not success:
            print("STDERR:")
            print(result.stderr[:500] + "..." if len(result.stderr) > 500 else result.stderr)
        
        return success
        
    except Exception as e:
        print_status("Dry run execution", False, f"Error: {e}")
        return False

def test_enhanced_options_parsing() -> bool:
    """Test parsing of enhanced kvm-auto options"""
    print_header("Testing Enhanced Options Parsing")
    
    try:
        sys.path.insert(0, '/home/ubuntu/cyris/src')
        from cyris.config.parser import CyRISConfigParser
        
        parser = CyRISConfigParser()
        config = parser.parse_file('test-kvm-auto-enhanced.yml')
        
        enhanced_guest = None
        for guest in config.guests:
            if guest.guest_id == 'ubuntu-enhanced':
                enhanced_guest = guest
                break
        
        if not enhanced_guest:
            print_status("Find enhanced guest", False, "ubuntu-enhanced not found")
            return False
        
        # Test enhanced options
        tests = [
            ('graphics_type', 'vnc'),
            ('graphics_port', 5900),
            ('graphics_listen', '0.0.0.0'),
            ('network_model', 'virtio'),
            ('os_variant', 'ubuntu22.04'),
            ('cpu_model', 'host'),
            ('console_type', 'pty'),
            ('boot_options', 'hd,menu=on'),
        ]
        
        all_passed = True
        for attr, expected in tests:
            if hasattr(enhanced_guest, attr):
                actual = getattr(enhanced_guest, attr)
                success = actual == expected
                details = f"Expected: {expected}, Got: {actual}"
                print_status(f"Option {attr}", success, details)
                if not success:
                    all_passed = False
            else:
                print_status(f"Option {attr}", False, "Attribute not found")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print_status("Enhanced options parsing", False, f"Error: {e}")
        return False

def generate_test_report(results: Dict[str, bool]) -> None:
    """Generate comprehensive test report"""
    print_header("Comprehensive Test Report")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    print(f"\nOverall Results: {passed}/{total} tests passed")
    print(f"Success Rate: {(passed/total)*100:.1f}%\n")
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    if passed == total:
        print("\n🎉 All tests passed! kvm-auto implementation is working correctly.")
    else:
        print(f"\n⚠️  {total-passed} test(s) failed. Review the output above for details.")
        print("\n📋 Recommended next steps:")
        if not results.get('Tool availability', True):
            print("   - Install missing virtualization tools")
            print("   - Run: sudo apt install libguestfs-tools virtinst")
        if not results.get('Image validation', True):
            print("   - Check virt-builder image availability")
            print("   - Run: virt-builder --list")
        if not results.get('Configuration parsing', True):
            print("   - Review YAML configuration syntax")
            print("   - Check field names and required values")

def main():
    """Run comprehensive kvm-auto test suite"""
    print("🧪 CyRIS kvm-auto Comprehensive Test Suite")
    print("Testing enhanced virt-install integration and configuration options")
    
    # Run all tests
    results = {}
    
    # Tool availability
    tools = check_virt_tools()
    results['Tool availability'] = all(tools.values())
    
    # YAML parsing
    results['YAML parsing'] = test_yaml_parsing()
    
    # Configuration integration
    results['Configuration parsing'] = test_cyris_config_parsing()
    
    # Image validation
    results['Image validation'] = test_image_validation()
    
    # Enhanced options
    results['Enhanced options'] = test_enhanced_options_parsing()
    
    # Dry run test
    results['Dry run execution'] = test_vm_creation_dry_run()
    
    # Generate report
    generate_test_report(results)
    
    # Exit with appropriate code
    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()