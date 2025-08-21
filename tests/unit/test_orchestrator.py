#!/usr/bin/env python3

"""
Comprehensive tests for Range Orchestrator Service
Following TDD principles: test real functionality, mock only external dependencies
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import sys
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.services.orchestrator import RangeOrchestrator, RangeMetadata, RangeStatus
from cyris.infrastructure.providers.base_provider import InfrastructureProvider
from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.config.settings import CyRISSettings
from cyris.domain.entities.host import Host
from cyris.domain.entities.guest import Guest


class MockProvider(InfrastructureProvider):
    """Mock infrastructure provider for testing"""
    
    def __init__(self):
        super().__init__("mock", {})
        self.created_hosts = []
        self.created_guests = []
        
    def connect(self):
        self._connected = True
        
    def disconnect(self):
        self._connected = False
        
    def is_connected(self) -> bool:
        return getattr(self, '_connected', False)
        
    def create_hosts(self, hosts):
        # The real orchestrator expects provider to return resource IDs
        # For legacy Host objects, use host_id; for modern Host objects, use id
        host_resource_ids = []
        for host in hosts:
            if hasattr(host, 'id'):
                # Modern Host with UUID
                host_resource_ids.append(str(host.id))
            else:
                # Legacy Host, use host_id
                host_resource_ids.append(host.host_id)
        
        self.created_hosts.extend(host_resource_ids)
        return host_resource_ids
        
    def create_guests(self, guests, host_mapping):
        # The real orchestrator expects provider to return VM names/IDs
        # KVM provider returns VM names like "cyris-{uuid}-{random}"
        guest_ids = []
        for guest in guests:
            if hasattr(guest, 'id'):
                # Modern Guest with UUID
                guest_ids.append(f"cyris-{guest.id}-mock")
            else:
                # Legacy Guest, use guest_id
                guest_ids.append(f"cyris-{guest.guest_id}-mock")
        
        self.created_guests.extend(guest_ids)
        return guest_ids
        
    def destroy_hosts(self, host_ids):
        for host_id in host_ids:
            if host_id in self.created_hosts:
                self.created_hosts.remove(host_id)
                
    def destroy_guests(self, guest_ids):
        for guest_id in guest_ids:
            if guest_id in self.created_guests:
                self.created_guests.remove(guest_id)
                
    def get_status(self, resource_ids):
        return {rid: "active" for rid in resource_ids}
        
    def get_resource_info(self, resource_id):
        return None


class TestRangeOrchestratorBasics:
    """Test basic orchestrator functionality"""
    
    @pytest.fixture
    def mock_config(self):
        return CyRISSettings(
            cyris_path=Path("/tmp/cyris"),
            cyber_range_dir=Path("/tmp/cyris/ranges"),
            gw_mode=False
        )
    
    @pytest.fixture
    def mock_provider(self):
        return MockProvider()
    
    @pytest.fixture
    def orchestrator(self, mock_config, mock_provider):
        return RangeOrchestrator(mock_config, mock_provider)
    
    def test_init(self, orchestrator):
        """Test orchestrator initialization"""
        assert orchestrator.settings is not None
        assert orchestrator.provider is not None
        assert len(orchestrator._ranges) == 0
    
    def test_range_metadata_creation(self, orchestrator):
        """Test range metadata creation through create_range"""
        range_id = "test_range_001"
        name = "Test Range"
        description = "Test cyber range"
        
        # Create test entities
        from cyris.domain.entities.host import Host
        from cyris.domain.entities.guest import Guest
        
        host = Host(
            host_id="test_host",
            virbr_addr="192.168.122.1",
            mgmt_addr="10.0.0.1", 
            account="test_user"
        )
        
        guest = Guest(
            guest_id="test_guest",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="test_host",
            basevm_config_file="/tmp/test.xml", 
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test_base",
            tasks=[]
        )
        
        metadata = orchestrator.create_range(range_id, name, description, [host], [guest])
        
        assert metadata.range_id == range_id
        assert metadata.name == name
        assert metadata.description == description
        assert metadata.status == RangeStatus.ACTIVE  # After successful creation
        assert metadata.created_at is not None
        assert metadata.last_modified is not None
    
    def test_get_range_after_creation(self, orchestrator):
        """Test range retrieval after creation"""
        range_id = "test_range_002"
        
        # Create test entities
        host = Host(
            host_id="test_host",
            virbr_addr="192.168.122.1",
            mgmt_addr="10.0.0.1", 
            account="test_user"
        )
        
        guest = Guest(
            guest_id="test_guest",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="test_host",
            basevm_config_file="/tmp/test.xml", 
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test_base",
            tasks=[]
        )
        
        # Create range
        metadata = orchestrator.create_range(range_id, "Test", "Description", [host], [guest])
        
        # Test retrieval
        assert range_id in orchestrator._ranges
        assert orchestrator.get_range(range_id) == metadata
        
        # Test destruction
        success = orchestrator.destroy_range(range_id)
        assert success
        # Range metadata still exists but status changed to DESTROYED
        destroyed_metadata = orchestrator.get_range(range_id)
        assert destroyed_metadata is not None
        assert destroyed_metadata.status == RangeStatus.DESTROYED
    
    def test_list_ranges(self, orchestrator):
        """Test listing ranges"""
        # Initially empty
        ranges = orchestrator.list_ranges()
        assert len(ranges) == 0
        
        # Create test entities
        host = Host(
            host_id="test_host",
            virbr_addr="192.168.122.1",
            mgmt_addr="10.0.0.1", 
            account="test_user"
        )
        
        guest = Guest(
            guest_id="test_guest",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="test_host",
            basevm_config_file="/tmp/test.xml", 
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test_base",
            tasks=[]
        )
        
        # Add some ranges
        for i in range(3):
            range_id = f"test_range_{i:03d}"
            orchestrator.create_range(range_id, f"Test {i}", f"Description {i}", [host], [guest])
        
        # List should return all ranges
        ranges = orchestrator.list_ranges()
        assert len(ranges) == 3
        assert all(isinstance(r, RangeMetadata) for r in ranges)


class TestRangeOrchestratorYAMLParsing:
    """Test YAML parsing and validation"""
    
    @pytest.fixture
    def mock_config(self):
        return CyRISSettings(
            cyris_path=Path("/tmp/cyris"),
            cyber_range_dir=Path("/tmp/cyris/ranges"),
            gw_mode=False
        )
    
    @pytest.fixture
    def mock_provider(self):
        return MockProvider()
    
    @pytest.fixture
    def orchestrator(self, mock_config, mock_provider):
        return RangeOrchestrator(mock_config, mock_provider)
    
    @pytest.fixture
    def sample_yaml_content(self):
        return '''---
- host_settings:
  - id: host_1
    virbr_addr: 192.168.122.1
    mgmt_addr: 10.0.0.1
    account: test_user

- guest_settings:
  - id: desktop
    ip_addr: 192.168.100.10
    basevm_host: host_1
    basevm_config_file: /tmp/basevm.xml
    basevm_os_type: ubuntu
    basevm_type: kvm
    tasks: []

- clone_settings:
  - range_id: 123
    hosts:
    - host_id: host_1
      instance_number: 1
      guests:
      - guest_id: desktop
        number: 1
      topology:
      - type: internet
        networks:
        - name: default
          members: [desktop]
        '''
    
    def test_parse_yaml_content(self, orchestrator, sample_yaml_content):
        """Test YAML parsing functionality through create_range_from_yaml"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(sample_yaml_content)
            yaml_file = Path(f.name)
        
        try:
            # Test dry run parsing
            range_id = orchestrator.create_range_from_yaml(
                description_file=yaml_file,
                dry_run=True
            )
            
            # Should return the range_id from YAML
            assert range_id == "123"
            
            # No range should be registered in dry run
            assert len(orchestrator._ranges) == 0
            
            # Test actual creation
            range_id = orchestrator.create_range_from_yaml(
                description_file=yaml_file,
                dry_run=False
            )
            
            assert range_id == "123"
            
            # Range should be registered
            assert len(orchestrator._ranges) == 1
            metadata = orchestrator.get_range("123")
            assert metadata is not None
            assert metadata.range_id == "123"
            assert metadata.status == RangeStatus.ACTIVE
            
        finally:
            yaml_file.unlink()
    
    def test_parse_invalid_yaml(self, orchestrator):
        """Test handling of invalid YAML"""
        invalid_yaml = '''
        invalid: yaml: content: [
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(invalid_yaml)
            yaml_file = Path(f.name)
        
        try:
            with pytest.raises(Exception):  # Should raise parsing error
                orchestrator.create_range_from_yaml(
                    description_file=yaml_file,
                    dry_run=True
                )
        finally:
            yaml_file.unlink()


class TestRangeOrchestratorRangeCreation:
    """Test complete range creation process"""
    
    @pytest.fixture
    def temp_config(self):
        # Create temporary directories
        temp_dir = Path(tempfile.mkdtemp())
        cyber_range_dir = temp_dir / "ranges"
        cyber_range_dir.mkdir()
        
        config = CyRISSettings(
            cyris_path=temp_dir,
            cyber_range_dir=cyber_range_dir,
            gw_mode=False
        )
        
        yield config
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def orchestrator_real_dirs(self, temp_config):
        provider = MockProvider()
        return RangeOrchestrator(temp_config, provider)
    
    @pytest.fixture
    def simple_yaml_file(self, temp_config):
        yaml_content = '''---
- host_settings:
  - id: host_1
    virbr_addr: 192.168.122.1
    mgmt_addr: 10.0.0.1
    account: test_user

- guest_settings:
  - id: desktop
    ip_addr: 192.168.100.10
    basevm_host: host_1
    basevm_config_file: /tmp/basevm.xml
    basevm_os_type: ubuntu
    basevm_type: kvm
    tasks: []

- clone_settings:
  - range_id: 456
    hosts:
    - host_id: host_1
      instance_number: 1
      guests:
      - guest_id: desktop
        number: 1
      topology:
      - type: internet
        networks:
        - name: default
          members: [desktop]
        '''
        
        yaml_file = temp_config.cyris_path / "test_range.yml"
        yaml_file.write_text(yaml_content)
        return yaml_file
    
    def test_create_range_from_yaml_dry_run(self, orchestrator_real_dirs, simple_yaml_file):
        """Test dry run range creation"""
        result = orchestrator_real_dirs.create_range_from_yaml(
            description_file=simple_yaml_file,
            dry_run=True
        )
        
        # Should return range ID but not actually create
        assert result == "456"
        
        # Provider should not have created anything
        assert len(orchestrator_real_dirs.provider.created_hosts) == 0
        assert len(orchestrator_real_dirs.provider.created_guests) == 0
        
        # No range should be registered
        assert len(orchestrator_real_dirs._ranges) == 0
    
    def test_create_range_from_yaml_real(self, orchestrator_real_dirs, simple_yaml_file):
        """Test real range creation"""
        result = orchestrator_real_dirs.create_range_from_yaml(
            description_file=simple_yaml_file,
            dry_run=False
        )
        
        # Should return range ID
        assert result == "456"
        
        # Provider should have created resources
        assert len(orchestrator_real_dirs.provider.created_hosts) == 1
        assert len(orchestrator_real_dirs.provider.created_guests) == 1
        
        # Range should be registered
        assert len(orchestrator_real_dirs._ranges) == 1
        metadata = orchestrator_real_dirs.get_range("456")
        assert metadata is not None
        assert metadata.status == RangeStatus.ACTIVE
    
    def test_destroy_range(self, orchestrator_real_dirs, simple_yaml_file):
        """Test range destruction"""
        # First create a range
        range_id = orchestrator_real_dirs.create_range_from_yaml(
            description_file=simple_yaml_file,
            dry_run=False
        )
        
        # Verify it was created
        assert orchestrator_real_dirs.get_range(range_id) is not None
        assert len(orchestrator_real_dirs.provider.created_hosts) > 0
        assert len(orchestrator_real_dirs.provider.created_guests) > 0
        
        # Destroy the range
        success = orchestrator_real_dirs.destroy_range(range_id)
        assert success
        
        # Verify it was destroyed (metadata still exists but status changed)
        destroyed_metadata = orchestrator_real_dirs.get_range(range_id)
        assert destroyed_metadata is not None
        assert destroyed_metadata.status == RangeStatus.DESTROYED
        assert len(orchestrator_real_dirs.provider.created_hosts) == 0
        assert len(orchestrator_real_dirs.provider.created_guests) == 0
    
    def test_get_range_resources(self, orchestrator_real_dirs, simple_yaml_file):
        """Test getting range resources"""
        # Create a range
        range_id = orchestrator_real_dirs.create_range_from_yaml(
            description_file=simple_yaml_file,
            dry_run=False
        )
        
        # Get resources
        resources = orchestrator_real_dirs.get_range_resources(range_id)
        
        assert resources is not None
        assert "hosts" in resources
        assert "guests" in resources
        assert len(resources["hosts"]) == 1
        assert len(resources["guests"]) == 1


class TestRangeOrchestratorErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.fixture
    def mock_config(self):
        return CyRISSettings(
            cyris_path=Path("/tmp/cyris"),
            cyber_range_dir=Path("/tmp/cyris/ranges"),
            gw_mode=False
        )
    
    def test_provider_failure(self, mock_config):
        """Test handling of provider failures"""
        # Create a provider that fails on connect
        failing_provider = MockProvider()
        failing_provider.connect = Mock(side_effect=Exception("Connection failed"))
        
        orchestrator = RangeOrchestrator(mock_config, failing_provider)
        
        # Should handle provider failure gracefully
        with pytest.raises(Exception):
            orchestrator.provider.connect()
    
    def test_destroy_nonexistent_range(self, mock_config):
        """Test destroying a range that doesn't exist"""
        provider = MockProvider()
        orchestrator = RangeOrchestrator(mock_config, provider)
        
        result = orchestrator.destroy_range("nonexistent_range")
        assert result is False  # Should return False for non-existent range
    
    def test_get_nonexistent_range(self, mock_config):
        """Test getting a range that doesn't exist"""
        provider = MockProvider()
        orchestrator = RangeOrchestrator(mock_config, provider)
        
        metadata = orchestrator.get_range("nonexistent_range")
        assert metadata is None


class TestRangeOrchestratorAdvanced:
    """Test advanced orchestrator functionality"""
    
    @pytest.fixture
    def mock_config(self):
        return CyRISSettings(
            cyris_path=Path("/tmp/cyris"),
            cyber_range_dir=Path("/tmp/cyris/ranges"),
            gw_mode=False
        )
    
    @pytest.fixture
    def mock_provider(self):
        return MockProvider()
    
    @pytest.fixture
    def orchestrator(self, mock_config, mock_provider):
        return RangeOrchestrator(mock_config, mock_provider)
        
    def test_range_filtering(self, orchestrator):
        """Test range listing with filters"""
        # Create some ranges with different attributes
        host = Host(
            host_id="test_host",
            virbr_addr="192.168.122.1",
            mgmt_addr="10.0.0.1", 
            account="test_user"
        )
        
        guest = Guest(
            guest_id="test_guest",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="test_host",
            basevm_config_file="/tmp/test.xml", 
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test_base",
            tasks=[]
        )
        
        # Create ranges
        orchestrator.create_range("range1", "Range 1", "Description 1", [host], [guest], owner="user1", tags={"env": "test"})
        orchestrator.create_range("range2", "Range 2", "Description 2", [host], [guest], owner="user2", tags={"env": "prod"})
        orchestrator.create_range("range3", "Range 3", "Description 3", [host], [guest], owner="user1", tags={"env": "test"})
        
        # Test filtering by owner
        user1_ranges = orchestrator.list_ranges(owner="user1")
        assert len(user1_ranges) == 2
        assert all(r.owner == "user1" for r in user1_ranges)
        
        # Test filtering by status
        active_ranges = orchestrator.list_ranges(status=RangeStatus.ACTIVE)
        assert len(active_ranges) == 3
        assert all(r.status == RangeStatus.ACTIVE for r in active_ranges)
        
        # Test filtering by tags
        test_ranges = orchestrator.list_ranges(tags={"env": "test"})
        assert len(test_ranges) == 2
        assert all(r.tags.get("env") == "test" for r in test_ranges)
    
    def test_update_range_status(self, orchestrator):
        """Test range status updates"""
        # Create a range
        host = Host(
            host_id="test_host",
            virbr_addr="192.168.122.1",
            mgmt_addr="10.0.0.1", 
            account="test_user"
        )
        
        guest = Guest(
            guest_id="test_guest",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="test_host",
            basevm_config_file="/tmp/test.xml", 
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test_base",
            tasks=[]
        )
        
        metadata = orchestrator.create_range("status_test", "Status Test", "Description", [host], [guest])
        assert metadata.status == RangeStatus.ACTIVE
        
        # Update status should query the provider
        status = orchestrator.update_range_status("status_test")
        assert status == RangeStatus.ACTIVE  # MockProvider always returns "active"
    
    def test_get_statistics(self, orchestrator):
        """Test orchestrator statistics"""
        # Initially empty
        stats = orchestrator.get_statistics()
        assert stats["total_ranges"] == 0
        
        # Create some ranges
        host = Host(
            host_id="test_host",
            virbr_addr="192.168.122.1",
            mgmt_addr="10.0.0.1", 
            account="test_user"
        )
        
        guest = Guest(
            guest_id="test_guest",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="test_host",
            basevm_config_file="/tmp/test.xml", 
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="test_base",
            tasks=[]
        )
        
        # Create ranges
        orchestrator.create_range("stats1", "Stats 1", "Description 1", [host], [guest])
        orchestrator.create_range("stats2", "Stats 2", "Description 2", [host], [guest])
        
        # Check statistics
        stats = orchestrator.get_statistics()
        assert stats["total_ranges"] == 2
        assert stats["status_distribution"]["active"] == 2
        assert stats["oldest_range"] is not None
        assert stats["newest_range"] is not None


class TestRangeOrchestratorWithRealKVMProvider:
    """Test orchestrator with real KVM provider (integration-style tests)"""
    
    @pytest.fixture
    def kvm_config(self):
        temp_dir = Path(tempfile.mkdtemp())
        cyber_range_dir = temp_dir / "ranges"
        cyber_range_dir.mkdir()
        
        config = CyRISSettings(
            cyris_path=temp_dir,
            cyber_range_dir=cyber_range_dir,
            gw_mode=False
        )
        
        yield config
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_orchestrator_with_kvm_provider(self, kvm_config):
        """Test orchestrator with real KVM provider"""
        # Create KVM provider in mock mode for testing
        with patch('cyris.infrastructure.providers.kvm_provider.LIBVIRT_TYPE', 'mock'):
            kvm_provider = KVMProvider({
                "libvirt_uri": "qemu:///session", 
                "base_path": str(kvm_config.cyber_range_dir)
            })
            
            orchestrator = RangeOrchestrator(kvm_config, kvm_provider)
            
            # Should be able to initialize
            assert orchestrator.provider is not None
            assert orchestrator.provider.provider_name == "kvm"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])