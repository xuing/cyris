#!/usr/bin/env python3
"""
Test script to validate legacy CyRIS core functionality
without requiring sudo privileges or actual deployment.
"""

import sys
import os
sys.path.insert(0, 'main')

def test_config_parsing():
    """Test configuration file parsing"""
    try:
        from parse_config import parse_config
        result = parse_config('CONFIG')
        
        print("✅ Configuration parsing:")
        print(f"   CyRIS Path: {result[0]}")
        print(f"   Cyber Range Dir: {result[1]}")
        print(f"   Gateway Mode: {result[2]}")
        return True
    except Exception as e:
        print(f"❌ Configuration parsing failed: {e}")
        return False

def test_yaml_parsing():
    """Test YAML description file parsing"""
    try:
        import yaml
        from entities import Host, Guest, CloneGuest
        
        # Test with basic.yml
        with open('examples/basic.yml', 'r') as f:
            doc = yaml.load(f, Loader=yaml.SafeLoader)
        
        hosts = []
        guests = []
        
        for element in doc:
            if 'host_settings' in element:
                for h in element['host_settings']:
                    host = Host(h['id'], h.get('virbr_addr'), h['mgmt_addr'], h['account'])
                    hosts.append(host)
                    
            if 'guest_settings' in element:
                for g in element['guest_settings']:
                    # Note: Guest constructor needs all parameters
                    guests.append(g)  # Store dict for now
                    
        print("✅ YAML parsing:")
        print(f"   Hosts: {len(hosts)} defined")
        print(f"   Guests: {len(guests)} defined")
        for host in hosts:
            print(f"   - Host {host.getHostId()} at {host.getMgmtAddr()}")
        return True
        
    except Exception as e:
        print(f"❌ YAML parsing failed: {e}")
        return False

def test_module_imports():
    """Test that all legacy modules can be imported"""
    modules_to_test = [
        'entities',
        'parse_config', 
        'modules',
        'storyboard'
    ]
    
    success = True
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ Module {module_name}: imported successfully")
        except Exception as e:
            print(f"❌ Module {module_name}: failed to import - {e}")
            success = False
            
    return success

def test_dependencies():
    """Test that required dependencies are available"""
    deps_to_test = [
        'paramiko',
        'boto3', 
        'yaml',
        'subprocess'
    ]
    
    success = True
    for dep_name in deps_to_test:
        try:
            __import__(dep_name)
            print(f"✅ Dependency {dep_name}: available")
        except Exception as e:
            print(f"❌ Dependency {dep_name}: missing - {e}")
            success = False
            
    return success

def main():
    """Run all legacy functionality tests"""
    print("🧪 Testing CyRIS Legacy Core Functionality")
    print("=" * 50)
    
    tests = [
        test_dependencies,
        test_module_imports,
        test_config_parsing,
        test_yaml_parsing
    ]
    
    results = []
    for test in tests:
        print()
        result = test()
        results.append(result)
        
    print()
    print("=" * 50)
    print("📊 Test Results:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All {total} tests PASSED!")
        print("✅ Legacy core functionality is working correctly")
        return True
    else:
        print(f"❌ {passed}/{total} tests passed")
        print(f"⚠️  {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)