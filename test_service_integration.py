#!/usr/bin/env python3
"""
Advanced Service Integration Tests

Tests complete workflows and service interactions using TDD principles.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "main"))

def test_end_to_end_workflow():
    """Test complete end-to-end cyber range creation workflow"""
    print("🧪 Testing end-to-end workflow...")
    
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from entities import Host, Guest
        
        # Create temporary working directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cyber_range_dir = temp_path / "cyber_range"
            cyber_range_dir.mkdir()
            
            # Create settings with temporary directory
            settings = CyRISSettings(
                cyris_path=project_root,
                cyber_range_dir=cyber_range_dir
            )
            
            # Create provider and orchestrator
            kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(cyber_range_dir)}
            provider = KVMProvider(kvm_config)
            orchestrator = RangeOrchestrator(settings, provider)
            
            # Create test entities
            hosts = [Host('test_host', '192.168.122.1', 'localhost', 'testuser')]
            guests = [Guest('test_guest', '192.168.1.100', 'password', 'test_host',
                           '/config.xml', 'linux', 'kvm', 'test_guest', [])]
            
            # Test range creation
            metadata = orchestrator.create_range(
                range_id="test_range_001",
                name="Test Range",
                description="End-to-end test range",
                hosts=hosts,
                guests=guests
            )
            
            assert metadata.range_id == "test_range_001"
            assert metadata.name == "Test Range"
            print("✅ End-to-end range creation successful")
            
            # Test range listing
            ranges = orchestrator.list_ranges()
            assert len(ranges) == 1
            assert ranges[0].range_id == "test_range_001"
            print("✅ Range listing successful")
            
            # Test range retrieval
            retrieved = orchestrator.get_range("test_range_001")
            assert retrieved is not None
            assert retrieved.name == "Test Range"
            print("✅ Range retrieval successful")
            
            # Test status update
            status = orchestrator.update_range_status("test_range_001")
            assert status is not None
            print("✅ Status update successful")
            
            # Test resource information
            resources = orchestrator.get_range_resources("test_range_001")
            assert resources is not None
            assert "hosts" in resources
            assert "guests" in resources
            print("✅ Resource information retrieval successful")
            
            # Test range destruction
            success = orchestrator.destroy_range("test_range_001")
            assert success == True
            print("✅ Range destruction successful")
            
            return True
            
    except Exception as e:
        print(f"❌ End-to-end workflow error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_yaml_workflow_integration():
    """Test YAML-based workflow integration"""
    print("\n🧪 Testing YAML workflow integration...")
    
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        # Create temporary working directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cyber_range_dir = temp_path / "cyber_range"
            cyber_range_dir.mkdir()
            
            settings = CyRISSettings(
                cyris_path=project_root,
                cyber_range_dir=cyber_range_dir
            )
            
            kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(cyber_range_dir)}
            provider = KVMProvider(kvm_config)
            orchestrator = RangeOrchestrator(settings, provider)
            
            # Test with actual example file
            yaml_file = Path("examples/basic.yml")
            if yaml_file.exists():
                # Test dry run
                result_dry = orchestrator.create_range_from_yaml(
                    description_file=yaml_file,
                    range_id=12345,
                    dry_run=True
                )
                assert result_dry == "12345"
                print("✅ YAML dry-run workflow successful")
                
                # Test actual creation
                result_create = orchestrator.create_range_from_yaml(
                    description_file=yaml_file,
                    range_id=12346,
                    dry_run=False
                )
                assert result_create == "12346"
                print("✅ YAML creation workflow successful")
                
                # Verify range was created
                ranges = orchestrator.list_ranges()
                assert len(ranges) == 1
                assert ranges[0].range_id == "12346"
                print("✅ YAML-created range verification successful")
                
            else:
                print("⚠️  examples/basic.yml not found, creating test YAML...")
                
                # Create test YAML
                test_yaml_content = """---
- host_settings:
  - id: test_host
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: testuser

- guest_settings:
  - id: test_desktop
    basevm_host: test_host
    basevm_config_file: /config.xml
    basevm_type: kvm

- clone_settings:
  - range_id: 54321
    hosts:
    - host_id: test_host
      instance_number: 1
      guests:
      - guest_id: test_desktop
        number: 1
"""
                test_yaml_file = temp_path / "test.yml"
                with open(test_yaml_file, 'w') as f:
                    f.write(test_yaml_content)
                
                result = orchestrator.create_range_from_yaml(
                    description_file=test_yaml_file,
                    dry_run=True
                )
                assert result == "54321"
                print("✅ Test YAML workflow successful")
            
            return True
            
    except Exception as e:
        print(f"❌ YAML workflow integration error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multi_range_management():
    """Test managing multiple ranges simultaneously"""
    print("\n🧪 Testing multi-range management...")
    
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from entities import Host, Guest
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cyber_range_dir = temp_path / "cyber_range"
            cyber_range_dir.mkdir()
            
            settings = CyRISSettings(
                cyris_path=project_root,
                cyber_range_dir=cyber_range_dir
            )
            
            kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(cyber_range_dir)}
            provider = KVMProvider(kvm_config)
            orchestrator = RangeOrchestrator(settings, provider)
            
            # Create multiple ranges
            for i in range(3):
                hosts = [Host(f'host_{i}', '192.168.122.1', 'localhost', 'testuser')]
                guests = [Guest(f'guest_{i}', '192.168.1.100', 'password', f'host_{i}',
                               '/config.xml', 'linux', 'kvm', f'guest_{i}', [])]
                
                metadata = orchestrator.create_range(
                    range_id=f"multi_range_{i:03d}",
                    name=f"Multi Range {i}",
                    description=f"Test range {i}",
                    hosts=hosts,
                    guests=guests
                )
                assert metadata.range_id == f"multi_range_{i:03d}"
            
            print("✅ Multiple range creation successful")
            
            # Test listing all ranges
            ranges = orchestrator.list_ranges()
            assert len(ranges) == 3
            print("✅ Multiple range listing successful")
            
            # Test statistics
            stats = orchestrator.get_statistics()
            assert stats['total_ranges'] == 3
            assert stats['status_distribution']['active'] == 3
            print("✅ Multiple range statistics successful")
            
            # Test individual range status updates
            for i in range(3):
                status = orchestrator.update_range_status(f"multi_range_{i:03d}")
                assert status is not None
            print("✅ Multiple range status updates successful")
            
            # Test destroying some ranges
            success = orchestrator.destroy_range("multi_range_001")
            assert success == True
            
            ranges_after_destroy = orchestrator.list_ranges()
            active_ranges = [r for r in ranges_after_destroy if r.status.value != 'destroyed']
            assert len(active_ranges) == 2
            print("✅ Selective range destruction successful")
            
            return True
            
    except Exception as e:
        print(f"❌ Multi-range management error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling_and_recovery():
    """Test error handling and recovery scenarios"""
    print("\n🧪 Testing error handling and recovery...")
    
    try:
        from src.cyris.config.settings import CyRISSettings
        from src.cyris.services.orchestrator import RangeOrchestrator
        from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
        from entities import Host, Guest
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cyber_range_dir = temp_path / "cyber_range"
            cyber_range_dir.mkdir()
            
            settings = CyRISSettings(
                cyris_path=project_root,
                cyber_range_dir=cyber_range_dir
            )
            
            kvm_config = {'connection_uri': 'qemu:///system', 'base_path': str(cyber_range_dir)}
            provider = KVMProvider(kvm_config)
            orchestrator = RangeOrchestrator(settings, provider)
            
            # Test duplicate range creation
            hosts = [Host('error_host', '192.168.122.1', 'localhost', 'testuser')]
            guests = [Guest('error_guest', '192.168.1.100', 'password', 'error_host',
                           '/config.xml', 'linux', 'kvm', 'error_guest', [])]
            
            # Create first range
            orchestrator.create_range(
                range_id="error_test_range",
                name="Error Test Range",
                description="For testing errors",
                hosts=hosts,
                guests=guests
            )
            
            # Try to create duplicate - should fail
            try:
                orchestrator.create_range(
                    range_id="error_test_range",
                    name="Duplicate Range",
                    description="Should fail",
                    hosts=hosts,
                    guests=guests
                )
                assert False, "Should have failed with ValueError"
            except ValueError as e:
                assert "already exists" in str(e)
                print("✅ Duplicate range creation error handling successful")
            
            # Test retrieving non-existent range
            non_existent = orchestrator.get_range("does_not_exist")
            assert non_existent is None
            print("✅ Non-existent range handling successful")
            
            # Test destroying non-existent range
            destroy_result = orchestrator.destroy_range("does_not_exist")
            assert destroy_result == False
            print("✅ Non-existent range destruction handling successful")
            
            # Test status update for non-existent range
            status = orchestrator.update_range_status("does_not_exist")
            assert status is None
            print("✅ Non-existent range status update handling successful")
            
            # Test invalid YAML file
            invalid_yaml_file = temp_path / "invalid.yml"
            with open(invalid_yaml_file, 'w') as f:
                f.write("invalid yaml content: [unclosed")
            
            try:
                orchestrator.create_range_from_yaml(
                    description_file=invalid_yaml_file,
                    dry_run=True
                )
                assert False, "Should have failed with YAML error"
            except Exception as e:
                print("✅ Invalid YAML error handling successful")
            
            return True
            
    except Exception as e:
        print(f"❌ Error handling test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cli_service_integration():
    """Test CLI and service layer integration"""
    print("\n🧪 Testing CLI service integration...")
    
    try:
        from src.cyris.cli.main import main
        import io
        import contextlib
        
        # Test CLI commands that use services
        commands_to_test = [
            (['validate'], "Validating CyRIS environment"),
            (['config-show'], "Current configuration"),
            (['list'], "No cyber ranges found"),  # Expected when no ranges exist
        ]
        
        for cmd, expected_output in commands_to_test:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                try:
                    main(cmd)
                except SystemExit:
                    pass  # Expected for some commands
            
            result = output.getvalue()
            assert expected_output in result, f"Command {cmd} failed: expected '{expected_output}' in output"
            print(f"✅ CLI command {' '.join(cmd)} integration successful")
        
        # Test dry-run create command
        yaml_file = Path("examples/basic.yml")
        if yaml_file.exists():
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                try:
                    main(['create', str(yaml_file), '--dry-run'])
                except SystemExit:
                    pass
            
            result = output.getvalue()
            assert "Validation successful" in result
            print("✅ CLI dry-run create integration successful")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI service integration error: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_advanced_integration_tests():
    """Run all advanced integration tests"""
    print("=" * 60)
    print("🚀 Starting Advanced Service Integration Tests")
    print("=" * 60)
    
    tests = [
        test_end_to_end_workflow,
        test_yaml_workflow_integration,
        test_multi_range_management,
        test_error_handling_and_recovery,
        test_cli_service_integration
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
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Advanced Integration Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("🎉 All advanced integration tests passed! Service layer fully verified!")
        return True
    else:
        print(f"⚠️  {failed} advanced tests failed. Issues need to be addressed.")
        return False

if __name__ == "__main__":
    success = run_advanced_integration_tests()
    sys.exit(0 if success else 1)