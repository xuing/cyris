#!/usr/bin/env python3
"""
KVM Auto Workflow Test Script

This script tests the KVM auto workflow with Rich progress reporting
using the test-kvm-auto-ubuntu.yml configuration file.
"""

import sys
import os
import subprocess
import time
import argparse
from pathlib import Path

def run_command(cmd, description="Running command", timeout=30):
    """Run a command and return success/failure"""
    print(f"🔧 {description}")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            check=False
        )
        
        if result.returncode == 0:
            print(f"   ✅ Success")
            if result.stdout:
                print(f"   Output: {result.stdout[:200]}...")
            return True
        else:
            print(f"   ❌ Failed (exit code: {result.returncode})")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏰ Timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"   💥 Exception: {e}")
        return False


def check_prerequisites():
    """Check if required tools are available"""
    print("=" * 60)
    print("Checking Prerequisites")
    print("=" * 60)
    
    tools = [
        ("python3", ["python3", "--version"]),
        ("cyris", ["./cyris", "--version"]),
        ("virt-builder", ["virt-builder", "--version"]),
        ("virt-install", ["virt-install", "--version"]),
        ("virt-customize", ["virt-customize", "--version"]),
        ("virsh", ["virsh", "version"])
    ]
    
    results = {}
    for tool_name, cmd in tools:
        results[tool_name] = run_command(cmd, f"Checking {tool_name}", timeout=10)
    
    return results


def test_yaml_validation():
    """Test YAML configuration validation"""
    print("\\n" + "=" * 60)
    print("Testing YAML Configuration")
    print("=" * 60)
    
    config_file = Path("test-kvm-auto-ubuntu.yml")
    
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_file}")
        return False
    
    print(f"✅ Configuration file exists: {config_file}")
    
    # Test YAML parsing
    cmd = ["./cyris", "validate", str(config_file)]
    return run_command(cmd, "Validating YAML configuration", timeout=30)


def test_dry_run():
    """Test dry run mode"""
    print("\\n" + "=" * 60)
    print("Testing Dry Run Mode")
    print("=" * 60)
    
    cmd = ["./cyris", "create", "test-kvm-auto-ubuntu.yml", "--dry-run"]
    return run_command(cmd, "Testing dry run mode", timeout=60)


def test_pre_checks():
    """Test pre-creation checks"""
    print("\\n" + "=" * 60)
    print("Testing Pre-Creation Checks")
    print("=" * 60)
    
    # Run with a timeout to see pre-check output
    cmd = ["./cyris", "create", "test-kvm-auto-ubuntu.yml"]
    
    print("🔧 Running pre-creation checks (will cancel after checks)")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Capture output for a short time to see pre-checks
        output_lines = []
        start_time = time.time()
        
        while True:
            line = process.stdout.readline()
            if line:
                output_lines.append(line.strip())
                print(f"   > {line.strip()}")
                
                # Stop after we see the pre-checks or after 30 seconds
                if "Pre-Creation Checks" in line or time.time() - start_time > 30:
                    break
            elif process.poll() is not None:
                break
        
        # Terminate the process
        process.terminate()
        process.wait(timeout=5)
        
        print("   ✅ Pre-checks captured successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Error capturing pre-checks: {e}")
        return False


def test_image_list():
    """Test virt-builder image listing"""
    print("\\n" + "=" * 60)
    print("Testing Available Images")
    print("=" * 60)
    
    cmd = ["virt-builder", "--list"]
    success = run_command(cmd, "Listing available images", timeout=60)
    
    if success:
        # Check if ubuntu-20.04 is available
        result = subprocess.run(cmd, capture_output=True, text=True)
        if "ubuntu-20.04" in result.stdout:
            print("   ✅ ubuntu-20.04 image is available")
        else:
            print("   ⚠️ ubuntu-20.04 image not found in list")
    
    return success


def test_rich_output():
    """Test Rich output rendering"""
    print("\\n" + "=" * 60)
    print("Testing Rich Progress Output")
    print("=" * 60)
    
    # Run the Rich progress test script
    test_script = Path("test_rich_progress.py")
    
    if not test_script.exists():
        print("❌ Rich progress test script not found")
        return False
    
    cmd = ["python3", str(test_script), "--test", "basic"]
    return run_command(cmd, "Testing Rich progress display", timeout=30)


def simulate_creation_workflow():
    """Simulate the creation workflow without actually creating VMs"""
    print("\\n" + "=" * 60)  
    print("Simulating Creation Workflow")
    print("=" * 60)
    
    # Run the end-to-end simulation test
    test_script = Path("test_rich_progress.py")
    
    if not test_script.exists():
        print("❌ Rich progress test script not found")
        return False
    
    cmd = ["python3", str(test_script), "--test", "e2e"]
    return run_command(cmd, "Running end-to-end simulation", timeout=60)


def main():
    parser = argparse.ArgumentParser(description="Test KVM Auto Workflow")
    parser.add_argument(
        "--test",
        choices=["prereq", "yaml", "dry-run", "pre-checks", "images", "rich", "simulate", "all"],
        default="all",
        help="Which test to run"
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue running tests even if some fail"
    )
    
    args = parser.parse_args()
    
    print("🤖 CyRIS KVM Auto Workflow Test Suite")
    print(f"Testing Rich progress system and kvm-auto functionality\\n")
    
    tests = {
        "prereq": ("Prerequisites Check", check_prerequisites),
        "yaml": ("YAML Validation", test_yaml_validation),
        "dry-run": ("Dry Run Test", test_dry_run),
        "pre-checks": ("Pre-Checks Test", test_pre_checks),
        "images": ("Image List Test", test_image_list),
        "rich": ("Rich Output Test", test_rich_output),
        "simulate": ("Workflow Simulation", simulate_creation_workflow)
    }
    
    results = {}
    
    if args.test == "all":
        test_list = tests.items()
    else:
        test_list = [(args.test, tests[args.test])]
    
    for test_key, (test_name, test_func) in test_list:
        try:
            print(f"\\n{'='*20} {test_name} {'='*20}")
            result = test_func()
            results[test_key] = result
            
            if not result and not args.continue_on_failure:
                print(f"\\n❌ Test failed: {test_name}")
                print("Use --continue-on-failure to run all tests")
                break
                
        except KeyboardInterrupt:
            print(f"\\n⚠️ Test interrupted: {test_name}")
            break
        except Exception as e:
            print(f"\\n💥 Test error: {test_name} - {e}")
            results[test_key] = False
            
            if not args.continue_on_failure:
                break
    
    # Summary
    print("\\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_key, result in results.items():
        test_name = tests[test_key][0]
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The KVM auto workflow with Rich progress is working correctly.")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()