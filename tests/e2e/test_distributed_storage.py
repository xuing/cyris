#!/usr/bin/env python3
"""
End-to-End Tests for Distributed Storage System
Tests the complete workflow: create → status → destroy with file validation
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

# Test imports
import sys
sys.path.append('/home/ubuntu/cyris/src')

from cyris.services.orchestrator import RangeOrchestrator, RangeMetadata, RangeStatus
from cyris.config.settings import CyRISSettings


class TestDistributedStorage(unittest.TestCase):
    """Test distributed storage system end-to-end"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for testing
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create test settings
        self.settings = CyRISSettings(
            cyber_range_dir=str(self.test_dir),
            cyris_path="/home/ubuntu/cyris"
        )
        
        # Mock provider for testing
        self.mock_provider = MockKVMProvider()
        
        # Create orchestrator
        self.orchestrator = RangeOrchestrator(self.settings, self.mock_provider)

    def tearDown(self):
        """Clean up test environment"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_range_creation_with_distributed_storage(self):
        """Test that range creation creates proper distributed storage structure"""
        # Create a test range
        range_id = "test-range-001"
        metadata = self.orchestrator.create_range(
            range_id=range_id,
            name="Test Range",
            description="Testing distributed storage",
            hosts=[],
            guests=[]
        )
        
        # Verify range directory structure
        range_dir = self.test_dir / range_id
        self.assertTrue(range_dir.exists())
        
        # Check metadata.json
        metadata_file = range_dir / 'metadata.json'
        self.assertTrue(metadata_file.exists())
        
        with open(metadata_file) as f:
            stored_metadata = json.load(f)
            
        # Validate metadata structure (cleaned up fields)
        expected_fields = {
            'range_id', 'name', 'description', 'created_at', 
            'status', 'last_modified', 'owner', 'tags'
        }
        self.assertEqual(set(stored_metadata.keys()), expected_fields)
        
        # Check resources.json
        resources_file = range_dir / 'resources.json'
        self.assertTrue(resources_file.exists())
        
        # Check directory structure
        self.assertTrue((range_dir / 'logs').exists())
        self.assertTrue((range_dir / 'disks').exists())

    def test_auto_discovery_on_startup(self):
        """Test that ranges are auto-discovered on orchestrator startup"""
        # Manually create a range directory with metadata
        range_id = "auto-discovered-range"
        range_dir = self.test_dir / range_id
        range_dir.mkdir()
        
        # Create metadata.json
        metadata = {
            "range_id": range_id,
            "name": "Auto Discovered Range",
            "description": "Testing auto-discovery",
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "last_modified": datetime.now().isoformat(),
            "owner": None,
            "tags": {"test": "auto-discovery"}
        }
        
        with open(range_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Create resources.json
        resources = {"hosts": [], "guests": ["test-vm"]}
        with open(range_dir / 'resources.json', 'w') as f:
            json.dump(resources, f, indent=2)
        
        # Create new orchestrator (triggers auto-discovery)
        new_orchestrator = RangeOrchestrator(self.settings, self.mock_provider)
        
        # Verify range was discovered
        discovered_ranges = new_orchestrator.list_ranges()
        self.assertEqual(len(discovered_ranges), 1)
        self.assertEqual(discovered_ranges[0].range_id, range_id)
        self.assertEqual(discovered_ranges[0].name, "Auto Discovered Range")

    def test_yaml_config_backup(self):
        """Test that YAML config files are backed up to range directories"""
        # Create a temporary YAML file
        yaml_content = """---
- host_settings:
  - id: localhost
    mgmt_addr: localhost

- guest_settings:
  - id: test_vm
    basevm_host: localhost

- clone_settings:
  - range_id: yaml-backup-test
"""
        yaml_file = self.test_dir / 'test-config.yml'
        with open(yaml_file, 'w') as f:
            f.write(yaml_content)
        
        # Create range first
        range_id = "yaml-backup-test"
        self.orchestrator.create_range(
            range_id=range_id,
            name="YAML Backup Test",
            description="Testing YAML backup functionality",
            hosts=[],
            guests=[]
        )
        
        # Now save metadata with YAML backup
        self.orchestrator._save_range_metadata(range_id, yaml_config_path=yaml_file)
        
        # Check that config.yml was created in range directory
        range_dir = self.test_dir / range_id
        config_backup = range_dir / 'config.yml'
        self.assertTrue(config_backup.exists())
        
        # Verify content matches
        with open(config_backup) as f:
            backed_up_content = f.read()
        self.assertEqual(backed_up_content, yaml_content)

    def test_range_list_includes_discovered_ranges(self):
        """Test that list command includes auto-discovered ranges"""
        # Create multiple ranges manually (simulating orphaned ranges)
        ranges_data = [
            ("range-001", "Range One"),
            ("range-002", "Range Two"),
            ("range-003", "Range Three")
        ]
        
        for range_id, name in ranges_data:
            range_dir = self.test_dir / range_id
            range_dir.mkdir()
            
            metadata = {
                "range_id": range_id,
                "name": name,
                "description": f"Test range {range_id}",
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "last_modified": datetime.now().isoformat(),
                "owner": None,
                "tags": {}
            }
            
            with open(range_dir / 'metadata.json', 'w') as f:
                json.dump(metadata, f)
            
            with open(range_dir / 'resources.json', 'w') as f:
                json.dump({"hosts": [], "guests": []}, f)
        
        # Create new orchestrator (auto-discover)
        new_orchestrator = RangeOrchestrator(self.settings, self.mock_provider)
        
        # Verify all ranges discovered
        discovered = new_orchestrator.list_ranges()
        self.assertEqual(len(discovered), 3)
        
        discovered_ids = {r.range_id for r in discovered}
        expected_ids = {"range-001", "range-002", "range-003"}
        self.assertEqual(discovered_ids, expected_ids)

    def test_metadata_structure_is_clean(self):
        """Test that metadata structure contains only essential fields"""
        # Create range
        range_id = "clean-metadata-test"
        metadata = self.orchestrator.create_range(
            range_id=range_id,
            name="Clean Metadata Test",
            description="Testing clean metadata structure",
            hosts=[],
            guests=[]
        )
        
        # Read metadata from file
        range_dir = self.test_dir / range_id
        with open(range_dir / 'metadata.json') as f:
            stored_metadata = json.load(f)
        
        # Ensure no unnecessary fields
        forbidden_fields = {'config_path', 'logs_path', 'provider_config'}
        actual_fields = set(stored_metadata.keys())
        
        for field in forbidden_fields:
            self.assertNotIn(field, actual_fields, f"Unnecessary field '{field}' found in metadata")
        
        # Ensure required fields present
        required_fields = {'range_id', 'name', 'description', 'created_at', 'status'}
        for field in required_fields:
            self.assertIn(field, actual_fields, f"Required field '{field}' missing from metadata")


class MockKVMProvider:
    """Mock KVM provider for testing"""
    
    def __init__(self):
        self.libvirt_uri = "qemu:///system"
    
    def create_hosts(self, *args, **kwargs):
        return True
    
    def create_guests(self, *args, **kwargs):
        return True
    
    def create_vm(self, *args, **kwargs):
        return True
    
    def destroy_vm(self, *args, **kwargs):
        return True
    
    def list_vms(self):
        return []


if __name__ == '__main__':
    unittest.main()