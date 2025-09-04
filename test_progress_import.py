#!/usr/bin/env python3
"""
Test Rich Progress Manager Import

Tests if we can import and use the RichProgressManager without full CyRIS dependencies.
"""

import sys
from pathlib import Path

# Add the src directory to the Python path for testing
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_import():
    """Test importing the Rich Progress Manager"""
    print("Testing Rich Progress Manager import...")
    
    try:
        # Try to import just the progress manager
        from cyris.core.rich_progress import RichProgressManager, ProgressLevel
        print("✅ RichProgressManager imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_basic_usage():
    """Test basic usage of the progress manager"""
    print("\\nTesting basic Rich Progress Manager usage...")
    
    try:
        from cyris.core.rich_progress import RichProgressManager, ProgressLevel
        
        # Create a progress manager
        progress = RichProgressManager("Test Operation")
        print("✅ Progress manager created")
        
        # Test without context managers (safer)
        progress.log_info("Testing info message")
        progress.log_success("Testing success message")
        progress.log_warning("Testing warning message")
        progress.log_error("Testing error message")
        
        # Test step management
        progress.add_step("test_step", "Testing step", total=100)
        progress.start_step("test_step")
        progress.update_step("test_step", completed=50)
        progress.complete_step("test_step")
        
        progress.complete()
        
        # Get summary
        summary = progress.get_summary()
        print(f"✅ Operation summary: {summary}")
        
        return True
        
    except Exception as e:
        print(f"❌ Usage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_managers():
    """Test context manager usage"""
    print("\\nTesting Rich Progress Manager with context managers...")
    
    try:
        from cyris.core.rich_progress import RichProgressManager
        
        progress = RichProgressManager("Context Test")
        
        print("Testing progress context...")
        with progress.progress_context():
            print("  Inside progress context")
            
            # Test without live context for now
            progress.log_info("Context test message")
            progress.add_step("ctx_step", "Context step")
            progress.start_step("ctx_step") 
            progress.complete_step("ctx_step")
        
        progress.complete()
        print("✅ Context manager test completed")
        return True
        
    except Exception as e:
        print(f"❌ Context manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("🧪 Rich Progress Manager Import Test")
    print("="*50)
    
    tests = [
        ("Import Test", test_import),
        ("Basic Usage", test_basic_usage), 
        ("Context Managers", test_context_managers)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\\n{test_name}:")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\\n" + "="*50)
    print("Test Results Summary")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 Rich Progress Manager is ready!")
    else:
        print("⚠️ Some issues need to be resolved")
    
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())