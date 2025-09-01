#!/usr/bin/env python3
"""
Comprehensive test runner for CyRIS TDD test suite.
Runs all test categories with coverage reporting and provides summary.
Updated to use properly organized tests in tests/ directory structure.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent, 
                              capture_output=False, text=True)
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n✅ {description} completed successfully in {duration:.1f}s")
            return True
        else:
            print(f"\n❌ {description} failed with exit code {result.returncode} after {duration:.1f}s")
            return False
            
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n❌ {description} failed with exception after {duration:.1f}s: {e}")
        return False


def main():
    """Run comprehensive test suite"""
    print("🚀 CyRIS Comprehensive TDD Test Suite")
    print(f"Working directory: {Path.cwd()}")
    
    results = {}
    
    # 1. Unit Tests
    results['unit'] = run_command([
        'python', '-m', 'pytest', 
        'tests/unit/',
        '-v',
        '--tb=short',
        '--maxfail=5'
    ], "Unit Tests")
    
    # 2. Integration Tests
    results['integration'] = run_command([
        'python', '-m', 'pytest',
        'tests/integration/',
        '-v', 
        '--tb=short',
        '--maxfail=3'
    ], "Integration Tests")
    
    # 3. E2E Tests
    results['e2e'] = run_command([
        'python', '-m', 'pytest',
        'tests/e2e/',
        '-v',
        '--tb=short',
        '--maxfail=3'
    ], "End-to-End Tests")
    
    # 4. Coverage Report
    results['coverage'] = run_command([
        'python', '-m', 'pytest',
        'tests/',
        '--cov=src/cyris',
        '--cov-report=term-missing',
        '--cov-report=html:htmlcov',
        '--cov-fail-under=80'
    ], "Test Coverage Analysis")
    
    # 5. Specific IP Discovery and Base Image Tests
    results['ip_discovery'] = run_command([
        'python', '-m', 'pytest',
        'tests/unit/test_simplified_ip_discovery.py',
        'tests/unit/test_base_image_setup.py',
        '-v',
        '--tb=long'
    ], "IP Discovery and Base Image Tests")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST RESULTS SUMMARY")
    print(f"{'='*60}")
    
    total_tests = len(results)
    passed_tests = sum(1 for success in results.values() if success)
    
    for test_type, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_type.upper():20} : {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} test suites passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! CyRIS TDD implementation is complete.")
        if results.get('coverage'):
            print("📈 Coverage report generated in htmlcov/ directory")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test suite(s) failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())