#!/usr/bin/env python3
"""
Test script to validate modern CyRIS service layer functionality.
This tests the refactored service components without requiring system setup.
"""

import sys
from pathlib import Path

def test_service_imports():
    """Test that all modern service modules can be imported"""
    modules_to_test = [
        ('src.cyris.config.settings', 'CyRISSettings'),
        ('src.cyris.services.orchestrator', 'RangeOrchestrator'),
        ('src.cyris.services.monitoring', 'MonitoringService'),
        ('src.cyris.services.cleanup_service', 'CleanupService'),
        ('src.cyris.tools.ssh_manager', 'SSHManager'),
        ('src.cyris.tools.user_manager', 'UserManager'),
        ('src.cyris.infrastructure.providers.kvm_provider', 'KVMProvider'),
        ('src.cyris.infrastructure.providers.aws_provider', 'AWSProvider'),
    ]
    
    success = True
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✅ {class_name}: imported successfully")
        except Exception as e:
            print(f"❌ {class_name}: failed to import - {e}")
            success = False
            
    return success

def test_settings_creation():
    """Test configuration settings creation"""
    try:
        from src.cyris.config.settings import CyRISSettings
        
        settings = CyRISSettings()
        print(f"✅ Settings created: cyris_path={settings.cyris_path}")
        print(f"   cyber_range_dir={settings.cyber_range_dir}")
        print(f"   gw_mode={settings.gw_mode}")
        
        return True
    except Exception as e:
        print(f"❌ Settings creation failed: {e}")
        return False

def test_infrastructure_providers():
    """Test infrastructure providers instantiation"""
    try:
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from src.cyris.infrastructure.providers.aws_provider import AWSProvider
        
        # Test KVM Provider
        kvm_settings = {
            'connection_uri': 'qemu:///system',
            'base_path': '/tmp/test_kvm'
        }
        kvm_provider = KVMProvider(kvm_settings)
        print("✅ KVMProvider: instantiated successfully")
        
        # Test AWS Provider  
        aws_settings = {
            'region': 'us-east-1',
            'access_key_id': 'test_key',
            'secret_access_key': 'test_secret'
        }
        aws_provider = AWSProvider(aws_settings)
        print("✅ AWSProvider: instantiated successfully")
        
        return True
    except Exception as e:
        print(f"❌ Infrastructure providers failed: {e}")
        return False

def test_tools_layer():
    """Test tools layer functionality"""
    try:
        from src.cyris.tools.ssh_manager import SSHManager
        from src.cyris.tools.user_manager import UserManager
        
        # Create SSH manager
        ssh_mgr = SSHManager(
            max_connections=10,
            key_dir=Path('/tmp/test_ssh'),
            connection_timeout=30
        )
        print("✅ SSHManager: instantiated successfully")
        
        # Create User manager
        user_mgr = UserManager(
            ssh_manager=ssh_mgr,
            config_dir=Path('/tmp/test_users')
        )
        print("✅ UserManager: instantiated successfully")
        
        return True
    except Exception as e:
        print(f"❌ Tools layer failed: {e}")
        return False

def test_services_layer():
    """Test services layer functionality"""
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.services.monitoring import MonitoringService
        from src.cyris.services.cleanup_service import CleanupService
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        # Create mock provider
        provider = KVMProvider({'connection_uri': 'test', 'base_path': '/tmp'})
        
        # Create settings
        settings = CyRISSettings()
        
        # Test Orchestrator
        orchestrator = RangeOrchestrator(settings, provider)
        print("✅ RangeOrchestrator: instantiated successfully")
        
        # Test Monitoring Service
        monitor = MonitoringService(
            metrics_retention_hours=24,
            collection_interval_seconds=60
        )
        print("✅ MonitoringService: instantiated successfully")
        
        # Test Cleanup Service
        cleanup = CleanupService(
            infrastructure_provider=provider,
            cyber_range_dir=Path('/tmp/test_cleanup')
        )
        print("✅ CleanupService: instantiated successfully")
        
        return True
    except Exception as e:
        print(f"❌ Services layer failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration():
    """Test integration between components"""
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from src.cyris.tools.ssh_manager import SSHManager
        from src.cyris.tools.user_manager import UserManager
        
        # Create integrated system
        settings = CyRISSettings()
        kvm_provider = KVMProvider({'connection_uri': 'qemu:///system', 'base_path': '/tmp'})
        orchestrator = RangeOrchestrator(settings, kvm_provider)
        
        ssh_mgr = SSHManager(max_connections=5)
        user_mgr = UserManager(ssh_mgr)
        
        print("✅ Component integration: successful")
        print(f"   Settings: {type(settings).__name__}")
        print(f"   Provider: {type(kvm_provider).__name__}")
        print(f"   Orchestrator: {type(orchestrator).__name__}")
        print(f"   SSH Manager: {type(ssh_mgr).__name__}")
        print(f"   User Manager: {type(user_mgr).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    """Run all modern service layer tests"""
    print("🧪 Testing CyRIS Modern Service Layer")
    print("=" * 50)
    
    tests = [
        test_service_imports,
        test_settings_creation,
        test_infrastructure_providers,
        test_tools_layer,
        test_services_layer,
        test_integration
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
        print("✅ Modern service layer is working correctly")
        return True
    else:
        print(f"❌ {passed}/{total} tests passed")
        print(f"⚠️  {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)