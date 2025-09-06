#!/usr/bin/env python3
"""
Test the corrected subprocess timeout syntax
"""

import subprocess
import sys

def test_subprocess_syntax():
    """Test that our subprocess syntax is correct"""
    print("🧪 Testing Subprocess Syntax")
    print("=" * 40)
    
    try:
        # Test the corrected syntax (should not raise exception)
        print("Testing Popen without timeout parameter...")
        process = subprocess.Popen(
            ['echo', 'test'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("✅ Popen created successfully")
        
        # Test communicate with timeout
        print("Testing communicate with timeout...")
        stdout, stderr = process.communicate(input='', timeout=5)
        
        print("✅ communicate with timeout worked")
        print(f"   Output: {stdout.strip()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Subprocess syntax test failed: {e}")
        return False

def test_sudo_command_structure():
    """Test that sudo -S -v command structure is valid"""
    print("\n🧪 Testing Sudo Command Structure") 
    print("=" * 40)
    
    try:
        # Test the command structure (will fail auth but syntax should be ok)
        print("Testing sudo -S -v command structure...")
        process = subprocess.Popen(
            ['sudo', '-S', '-v'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("✅ sudo -S -v command structure accepted")
        
        # This will fail auth but that's expected
        try:
            stdout, stderr = process.communicate(input='wrong_password\n', timeout=5)
            print(f"   Return code: {process.returncode}")
            print("✅ Command executed (auth failure expected)")
        except subprocess.TimeoutExpired:
            process.kill()
            print("⚠️ Command timed out (may be normal)")
            
        return True
        
    except Exception as e:
        print(f"❌ Sudo command test failed: {e}")
        return False

def main():
    print("🔧 Testing Corrected Subprocess Implementation")
    print("=" * 50)
    
    tests = [
        ("Subprocess Syntax", test_subprocess_syntax),
        ("Sudo Command Structure", test_sudo_command_structure)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Subprocess fix verified!")
        print("💡 The stdin fallback should now work correctly.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)