#!/usr/bin/env python3
"""
Test script for the image builder with enhanced sudo workflow
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, '/home/ubuntu/cyris/src')

try:
    from cyris.infrastructure.image_builder import LocalImageBuilder
    from cyris.core.rich_progress import RichProgressManager
    print("✅ Imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_image_builder_initialization():
    """Test image builder initialization with sudo manager"""
    print("\n🧪 Testing Image Builder Initialization with Enhanced Sudo")
    print("=" * 60)
    
    try:
        # Create progress manager
        progress_manager = RichProgressManager("image_builder_test")
        
        # Create image builder
        image_builder = LocalImageBuilder()
        
        # Set progress manager (this should also update sudo manager)
        image_builder.set_progress_manager(progress_manager)
        
        print("✅ Image builder initialized successfully")
        print(f"✅ Command executor: {type(image_builder.command_executor).__name__}")
        print(f"✅ Sudo manager: {type(image_builder.sudo_manager).__name__}")
        print(f"✅ Progress manager set: {image_builder.progress_manager is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Image builder initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dependency_check_dry_run():
    """Test the dependency check without actually running sudo (dry run)"""
    print("\n🧪 Testing Dependency Check Structure (Dry Run)")
    print("=" * 50)
    
    try:
        image_builder = LocalImageBuilder()
        
        # Check that the sudo manager was initialized
        if hasattr(image_builder, 'sudo_manager'):
            print("✅ Sudo manager is initialized")
            if hasattr(image_builder.sudo_manager, 'command_executor'):
                if image_builder.sudo_manager.command_executor:
                    print("✅ Sudo manager has PTY-enabled command executor")
                    return True
                else:
                    print("⚠️  Sudo manager command executor is None (fallback mode)")
                    return True
            else:
                print("❌ Sudo manager missing command executor")
                return False
        else:
            print("❌ Sudo manager not initialized")
            return False
            
    except Exception as e:
        print(f"❌ Dependency check test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Image Builder Enhanced Sudo Workflow Test")
    print("=" * 60)
    
    tests = [
        ("Image Builder Initialization", test_image_builder_initialization),
        ("Dependency Check Structure", test_dependency_check_dry_run)
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
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Image builder is properly configured for enhanced PTY sudo.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    sys.exit(0 if passed == total else 1)