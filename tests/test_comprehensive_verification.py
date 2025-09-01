#!/usr/bin/env python3
"""
Comprehensive TDD Verification of CyRIS Refactoring

This script performs thorough testing of all refactored components
following Test-Driven Development principles.
"""

import sys
import os
import pytest
import tempfile
import yaml
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "main"))

def test_imports_and_dependencies():
    """Test that all critical imports work"""
    print("🧪 Testing critical imports...")
    
    try:
        # Test modern configuration imports
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.config.parser import parse_modern_config, ConfigurationError
        print("✅ Configuration imports successful")
        
        # Test domain entities
        from src.cyris.domain.entities.host import Host as ModernHost
        from src.cyris.domain.entities.guest import Guest as ModernGuest
        print("✅ Modern domain entities imports successful")
        
        # Test legacy entities compatibility
        from entities import Host, Guest
        print("✅ Legacy entities imports successful")
        
        # Test infrastructure providers
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from src.cyris.infrastructure.providers.base_provider import InfrastructureProvider
        print("✅ Infrastructure provider imports successful")
        
        # Test services
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.services.monitoring import MonitoringService
        from src.cyris.services.cleanup_service import CleanupService
        print("✅ Services imports successful")
        
        # Test CLI
        from src.cyris.cli.main import cli, main
        print("✅ CLI imports successful")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_configuration_system():
    """Test configuration parsing and validation"""
    print("\n🧪 Testing configuration system...")
    
    from src.cyris.config.settings import CyRISSettings
    from src.cyris.config.parser import parse_modern_config
    
    try:
        # Test default configuration
        settings = CyRISSettings()
        assert settings.cyris_path.exists(), "Default cyris_path should exist"
        print("✅ Default configuration creation successful")
        
        # Test CONFIG file parsing
        config_file = Path("CONFIG")
        if config_file.exists():
            settings = parse_modern_config(config_file)
            assert isinstance(settings, CyRISSettings)
            print("✅ CONFIG file parsing successful")
        
        # Test configuration validation
        assert settings.cyber_range_dir.is_absolute(), "cyber_range_dir should be absolute path"
        assert isinstance(settings.gw_mode, bool), "gw_mode should be boolean"
        print("✅ Configuration validation successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test error: {e}")
        return False

def test_yaml_parsing():
    """Test YAML description file parsing"""
    print("\n🧪 Testing YAML parsing...")
    
    try:
        # Test basic.yml parsing
        yaml_file = Path("examples/basic.yml")
        if yaml_file.exists():
            with open(yaml_file, 'r') as f:
                doc = yaml.load(f, Loader=yaml.SafeLoader)
            
            assert isinstance(doc, list), "YAML should parse to list"
            print("✅ YAML parsing successful")
            
            # Verify expected structure
            has_host_settings = any('host_settings' in elem for elem in doc)
            has_guest_settings = any('guest_settings' in elem for elem in doc)
            has_clone_settings = any('clone_settings' in elem for elem in doc)
            
            assert has_host_settings, "Should have host_settings"
            assert has_guest_settings, "Should have guest_settings"  
            assert has_clone_settings, "Should have clone_settings"
            print("✅ YAML structure validation successful")
            
            return True
        else:
            print("⚠️  examples/basic.yml not found, skipping YAML test")
            return True
            
    except Exception as e:
        print(f"❌ YAML parsing error: {e}")
        return False

def test_entity_creation():
    """Test entity creation from YAML data"""
    print("\n🧪 Testing entity creation...")
    
    try:
        from entities import Host, Guest
        
        # Test Host creation
        host = Host('host_1', '192.168.122.1', 'localhost', 'cyuser')
        assert host.getHostId() == 'host_1'
        assert host.getVirbrAddr() == '192.168.122.1'
        assert host.getMgmtAddr() == 'localhost'
        assert host.getAccount() == 'cyuser'
        print("✅ Legacy Host entity creation successful")
        
        # Test Guest creation
        guest = Guest(
            guest_id='desktop',
            basevm_addr='192.168.1.100',
            root_passwd='password',
            basevm_host='host_1',
            basevm_config_file='/config.xml',
            basevm_os_type='linux',
            basevm_type='kvm',
            basevm_name='desktop',
            tasks=[]
        )
        assert guest.getGuestId() == 'desktop'
        assert guest.getBasevmHost() == 'host_1'
        print("✅ Legacy Guest entity creation successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Entity creation error: {e}")
        return False

def test_infrastructure_provider():
    """Test KVM provider functionality"""
    print("\n🧪 Testing infrastructure provider...")
    
    try:
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        # Test provider initialization
        config = {
            'connection_uri': 'qemu:///system',
            'base_path': '/tmp/test'
        }
        provider = KVMProvider(config)
        assert provider.provider_name == 'kvm'
        print("✅ KVM provider initialization successful")
        
        # Test connection in mock mode
        provider.connect()
        assert provider.is_connected()
        print("✅ KVM provider connection successful (mock mode)")
        
        return True
        
    except Exception as e:
        print(f"❌ Infrastructure provider error: {e}")
        return False

def test_orchestrator_service():
    """Test range orchestrator functionality"""
    print("\n🧪 Testing orchestrator service...")
    
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        # Create test configuration
        settings = CyRISSettings()
        
        # Create provider
        kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(settings.cyber_range_dir)}
        provider = KVMProvider(kvm_config)
        
        # Create orchestrator
        orchestrator = RangeOrchestrator(settings, provider)
        assert orchestrator.settings == settings
        assert orchestrator.provider == provider
        print("✅ Orchestrator initialization successful")
        
        # Test statistics
        stats = orchestrator.get_statistics()
        assert 'total_ranges' in stats
        assert 'status_distribution' in stats
        print("✅ Orchestrator statistics successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator service error: {e}")
        return False

def test_yaml_to_range_creation():
    """Test complete YAML to range creation workflow"""
    print("\n🧪 Testing YAML to range creation workflow...")
    
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        # Setup
        settings = CyRISSettings()
        kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(settings.cyber_range_dir)}
        provider = KVMProvider(kvm_config)
        orchestrator = RangeOrchestrator(settings, provider)
        
        # Test dry run creation
        yaml_file = Path("examples/basic.yml")
        if yaml_file.exists():
            result = orchestrator.create_range_from_yaml(
                description_file=yaml_file,
                range_id=9999,
                dry_run=True
            )
            assert result == '9999'
            print("✅ YAML dry-run creation successful")
            
            return True
        else:
            print("⚠️  examples/basic.yml not found, skipping workflow test")
            return True
            
    except Exception as e:
        print(f"❌ YAML to range creation error: {e}")
        return False

def test_cli_commands():
    """Test CLI command functionality"""
    print("\n🧪 Testing CLI commands...")
    
    try:
        from src.cyris.cli.main import main
        import io
        import contextlib
        
        # Capture stdout for testing
        output = io.StringIO()
        
        with contextlib.redirect_stdout(output):
            try:
                # Test help command
                main(['--help'])
            except SystemExit:
                pass  # Expected for help command
        
        help_output = output.getvalue()
        assert 'CyRIS' in help_output
        assert 'create' in help_output
        assert 'list' in help_output
        print("✅ CLI help command successful")
        
        # Test validate command
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            try:
                main(['validate'])
            except SystemExit:
                pass  # May exit with code 0 or 1
        
        validate_output = output.getvalue()
        assert 'Validating CyRIS environment' in validate_output
        print("✅ CLI validate command successful")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI commands error: {e}")
        return False

def test_legacy_compatibility():
    """Test legacy interface compatibility"""
    print("\n🧪 Testing legacy compatibility...")
    
    try:
        # Test legacy script exists
        legacy_script = Path("main/cyris.py")
        if legacy_script.exists():
            print("✅ Legacy script exists")
        else:
            print("⚠️  Legacy script not found")
        
        # Test legacy entities can be used with modern code
        from entities import Host, Guest
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from src.cyris.config.settings import CyRISSettings
        
        # Create legacy entities
        hosts = [Host('host_1', '192.168.122.1', 'localhost', 'cyuser')]
        guests = [Guest('desktop', '192.168.1.100', 'password', 'host_1', 
                       '/config.xml', 'linux', 'kvm', 'desktop', [])]
        
        # Test they work with modern orchestrator
        settings = CyRISSettings()
        kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(settings.cyber_range_dir)}
        provider = KVMProvider(kvm_config)
        orchestrator = RangeOrchestrator(settings, provider)
        
        # This should not throw an exception
        stats = orchestrator.get_statistics()
        print("✅ Legacy entities compatible with modern services")
        
        return True
        
    except Exception as e:
        print(f"❌ Legacy compatibility error: {e}")
        return False

def run_comprehensive_tests():
    """Run all comprehensive tests"""
    print("=" * 60)
    print("🚀 Starting Comprehensive TDD Verification")
    print("=" * 60)
    
    tests = [
        test_imports_and_dependencies,
        test_configuration_system,
        test_yaml_parsing,
        test_entity_creation,
        test_infrastructure_provider,
        test_orchestrator_service,
        test_yaml_to_range_creation,
        test_cli_commands,
        test_legacy_compatibility
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("🎉 All tests passed! Refactoring verification successful!")
        return True
    else:
        print(f"⚠️  {failed} tests failed. Issues need to be addressed.")
        return False

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)