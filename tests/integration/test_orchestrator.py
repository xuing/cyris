"""
Integration tests for RangeOrchestrator service.

These tests verify that the orchestrator properly coordinates between
different components to create and manage cyber ranges.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime
import logging

from src.cyris.services.orchestrator import RangeOrchestrator, RangeStatus, RangeMetadata
from src.cyris.config.settings import CyRISSettings
from src.cyris.domain.entities.host import Host
from src.cyris.domain.entities.guest import Guest


class MockInfrastructureProvider:
    """Mock infrastructure provider for testing"""
    
    def __init__(self):
        self.created_hosts = []
        self.created_guests = []
        self.destroyed_hosts = []
        self.destroyed_guests = []
        self.host_statuses = {}
        self.guest_statuses = {}
        self.libvirt_uri = "qemu:///session"  # Mock libvirt URI
    
    def create_hosts(self, hosts):
        host_ids = [f"host-{host.host_id}" for host in hosts]
        self.created_hosts.extend(host_ids)
        for host_id in host_ids:
            self.host_statuses[host_id] = "active"
        return host_ids
    
    def create_guests(self, guests, host_mapping):
        guest_ids = [f"guest-{guest.guest_id}" for guest in guests]
        self.created_guests.extend(guest_ids)
        for guest_id in guest_ids:
            self.guest_statuses[guest_id] = "active"
        return guest_ids
    
    def destroy_hosts(self, host_ids):
        self.destroyed_hosts.extend(host_ids)
        for host_id in host_ids:
            self.host_statuses[host_id] = "terminated"
    
    def destroy_guests(self, guest_ids):
        self.destroyed_guests.extend(guest_ids)
        for guest_id in guest_ids:
            self.guest_statuses[guest_id] = "terminated"
    
    def get_status(self, resource_ids):
        status_map = {}
        for resource_id in resource_ids:
            if resource_id in self.host_statuses:
                status_map[resource_id] = self.host_statuses[resource_id]
            elif resource_id in self.guest_statuses:
                status_map[resource_id] = self.guest_statuses[resource_id]
            else:
                status_map[resource_id] = "not_found"
        return status_map


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def cyris_settings(temp_dir):
    """Create test CyRIS settings"""
    return CyRISSettings(
        cyber_range_dir=temp_dir / "cyber_range",
        gw_mgmt_addr="192.168.1.1",
        gw_account="cyris",
        cyris_path=temp_dir
    )


@pytest.fixture
def mock_provider():
    """Create mock infrastructure provider"""
    return MockInfrastructureProvider()


@pytest.fixture
def orchestrator(cyris_settings, mock_provider):
    """Create orchestrator instance"""
    logger = logging.getLogger("test_orchestrator")
    return RangeOrchestrator(cyris_settings, mock_provider, logger)


@pytest.fixture
def sample_hosts():
    """Create sample host configurations"""
    return [
        Host(
            host_id="web-server",
            mgmt_addr="192.168.1.10",
            virbr_addr="10.0.0.1",
            account="cyris"
        ),
        Host(
            host_id="db-server", 
            mgmt_addr="192.168.1.11",
            virbr_addr="10.0.0.2",
            account="cyris"
        )
    ]


@pytest.fixture
def sample_guests():
    """Create sample guest configurations"""
    from cyris.domain.entities.guest import OSType, BaseVMType
    return [
        Guest(
            guest_id="web-vm",
            basevm_host="web-server",
            basevm_config_file="/path/to/web.xml",
            basevm_os_type=OSType.UBUNTU_20,
            basevm_type=BaseVMType.KVM,
            ip_addr="10.0.0.10"
        ),
        Guest(
            guest_id="db-vm",
            basevm_host="db-server", 
            basevm_config_file="/path/to/db.xml",
            basevm_os_type=OSType.UBUNTU_20,
            basevm_type=BaseVMType.KVM,
            ip_addr="10.0.0.11"
        )
    ]


class TestRangeOrchestrator:
    """Test RangeOrchestrator functionality"""
    
    def test_create_range_success(self, orchestrator, sample_hosts, sample_guests):
        """Test successful range creation"""
        # Create range
        metadata = orchestrator.create_range(
            range_id="test-range-1",
            name="Test Range",
            description="Test range for integration testing",
            hosts=sample_hosts,
            guests=sample_guests,
            owner="test-user",
            tags={"environment": "test", "purpose": "integration"}
        )
        
        # Verify metadata
        assert metadata.range_id == "test-range-1"
        assert metadata.name == "Test Range"
        assert metadata.description == "Test range for integration testing"
        assert metadata.status == RangeStatus.ACTIVE
        assert metadata.owner == "test-user"
        assert metadata.tags["environment"] == "test"
        assert isinstance(metadata.created_at, datetime)
        
        # Verify infrastructure was created
        provider = orchestrator.provider
        assert len(provider.created_hosts) == 2
        assert len(provider.created_guests) == 2
        assert "host-web-server" in provider.created_hosts
        assert "host-db-server" in provider.created_hosts
        assert "guest-web-vm" in provider.created_guests
        assert "guest-db-vm" in provider.created_guests
        
        # Verify resource tracking
        resources = orchestrator.get_range_resources("test-range-1")
        assert resources is not None
        assert len(resources["hosts"]) == 2
        assert len(resources["guests"]) == 2
    
    def test_create_range_duplicate_id(self, orchestrator, sample_hosts, sample_guests):
        """Test creating range with duplicate ID fails"""
        # Create first range
        orchestrator.create_range(
            range_id="duplicate-range",
            name="First Range",
            description="First range",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Try to create second range with same ID
        with pytest.raises(ValueError, match="Range duplicate-range already exists"):
            orchestrator.create_range(
                range_id="duplicate-range",
                name="Second Range", 
                description="Second range",
                hosts=sample_hosts,
                guests=sample_guests
            )
    
    def test_create_range_infrastructure_failure(self, orchestrator, sample_hosts, sample_guests):
        """Test range creation with infrastructure failure"""
        # Configure provider to fail host creation
        orchestrator.provider.create_hosts = Mock(side_effect=Exception("Host creation failed"))
        
        # Attempt to create range
        with pytest.raises(RuntimeError, match="Range creation failed"):
            orchestrator.create_range(
                range_id="failing-range",
                name="Failing Range",
                description="Range that will fail",
                hosts=sample_hosts,
                guests=sample_guests
            )
        
        # Verify range is marked as error
        metadata = orchestrator.get_range("failing-range")
        assert metadata is not None
        assert metadata.status == RangeStatus.ERROR
    
    def test_get_range(self, orchestrator, sample_hosts, sample_guests):
        """Test retrieving range metadata"""
        # Create range
        created_metadata = orchestrator.create_range(
            range_id="get-test-range",
            name="Get Test Range",
            description="Range for get testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Retrieve range
        retrieved_metadata = orchestrator.get_range("get-test-range")
        
        assert retrieved_metadata is not None
        assert retrieved_metadata.range_id == created_metadata.range_id
        assert retrieved_metadata.name == created_metadata.name
        assert retrieved_metadata.status == created_metadata.status
        
        # Test non-existent range
        assert orchestrator.get_range("non-existent") is None
    
    def test_list_ranges(self, orchestrator, sample_hosts, sample_guests):
        """Test listing ranges with filters"""
        # Create multiple ranges
        orchestrator.create_range(
            range_id="range-1",
            name="Range 1",
            description="First range",
            hosts=sample_hosts,
            guests=sample_guests,
            owner="user1",
            tags={"env": "test"}
        )
        
        orchestrator.create_range(
            range_id="range-2", 
            name="Range 2",
            description="Second range",
            hosts=sample_hosts,
            guests=sample_guests,
            owner="user2",
            tags={"env": "prod"}
        )
        
        orchestrator.create_range(
            range_id="range-3",
            name="Range 3", 
            description="Third range",
            hosts=sample_hosts,
            guests=sample_guests,
            owner="user1",
            tags={"env": "test"}
        )
        
        # Test listing all ranges
        all_ranges = orchestrator.list_ranges()
        assert len(all_ranges) == 3
        
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
    
    def test_update_range_status(self, orchestrator, sample_hosts, sample_guests):
        """Test updating range status"""
        # Create range
        orchestrator.create_range(
            range_id="status-test-range",
            name="Status Test Range",
            description="Range for status testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Update status
        status = orchestrator.update_range_status("status-test-range")
        assert status == RangeStatus.ACTIVE
        
        # Change provider status to simulate error
        provider = orchestrator.provider
        for resource_id in provider.host_statuses:
            provider.host_statuses[resource_id] = "error"
        
        # Update status again
        status = orchestrator.update_range_status("status-test-range")
        assert status == RangeStatus.ERROR
        
        # Test non-existent range
        status = orchestrator.update_range_status("non-existent")
        assert status is None
    
    def test_destroy_range(self, orchestrator, sample_hosts, sample_guests):
        """Test range destruction"""
        # Create range
        orchestrator.create_range(
            range_id="destroy-test-range",
            name="Destroy Test Range",
            description="Range for destruction testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Verify range exists and is active
        metadata = orchestrator.get_range("destroy-test-range")
        assert metadata is not None
        assert metadata.status == RangeStatus.ACTIVE
        
        # Destroy range
        success = orchestrator.destroy_range("destroy-test-range")
        assert success is True
        
        # Verify range is marked as destroyed
        metadata = orchestrator.get_range("destroy-test-range")
        assert metadata.status == RangeStatus.DESTROYED
        
        # Verify infrastructure was cleaned up
        provider = orchestrator.provider
        assert len(provider.destroyed_hosts) == 2
        assert len(provider.destroyed_guests) == 2
        
        # Test destroying non-existent range
        success = orchestrator.destroy_range("non-existent")
        assert success is False
    
    def test_destroy_range_with_error(self, orchestrator, sample_hosts, sample_guests):
        """Test range destruction with infrastructure error"""
        # Create range
        orchestrator.create_range(
            range_id="error-destroy-range",
            name="Error Destroy Range", 
            description="Range for error destruction testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Configure provider to fail destruction
        orchestrator.provider.destroy_guests = Mock(side_effect=Exception("Destruction failed"))
        
        # Attempt to destroy range
        success = orchestrator.destroy_range("error-destroy-range")
        assert success is False
        
        # Verify range is marked as error
        metadata = orchestrator.get_range("error-destroy-range")
        assert metadata.status == RangeStatus.ERROR
    
    def test_get_statistics(self, orchestrator, sample_hosts, sample_guests):
        """Test orchestrator statistics"""
        # Initially no ranges
        stats = orchestrator.get_statistics()
        assert stats["total_ranges"] == 0
        assert stats["status_distribution"][RangeStatus.ACTIVE.value] == 0
        
        # Create some ranges
        orchestrator.create_range(
            range_id="stats-range-1",
            name="Stats Range 1",
            description="First stats range",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        orchestrator.create_range(
            range_id="stats-range-2",
            name="Stats Range 2",
            description="Second stats range", 
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Check updated statistics
        stats = orchestrator.get_statistics()
        assert stats["total_ranges"] == 2
        assert stats["status_distribution"][RangeStatus.ACTIVE.value] == 2
        assert stats["status_distribution"][RangeStatus.CREATING.value] == 0
        assert stats["oldest_range"] is not None
        assert stats["newest_range"] is not None
    
    def test_range_directory_creation(self, orchestrator, sample_hosts, sample_guests, temp_dir):
        """Test that range directories are created properly"""
        # Create range
        metadata = orchestrator.create_range(
            range_id="directory-test-range",
            name="Directory Test Range",
            description="Range for directory testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Verify range directory exists
        range_dir = temp_dir / "cyber_range" / "directory-test-range"
        assert range_dir.exists()
        assert range_dir.is_dir()
        
        # Verify logs directory exists
        logs_dir = Path(metadata.logs_path)
        assert logs_dir.exists()
        assert logs_dir.is_dir()
        assert logs_dir.parent == range_dir
        
    def test_concurrent_range_operations(self, orchestrator, sample_hosts, sample_guests):
        """Test concurrent range operations"""
        import threading
        import time
        
        results = {}
        errors = {}
        
        def create_range(range_id):
            try:
                metadata = orchestrator.create_range(
                    range_id=f"concurrent-{range_id}",
                    name=f"Concurrent Range {range_id}",
                    description=f"Range {range_id} for concurrency testing",
                    hosts=sample_hosts,
                    guests=sample_guests
                )
                results[range_id] = metadata.status
            except Exception as e:
                errors[range_id] = str(e)
        
        # Create multiple ranges concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_range, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 5
        assert len(errors) == 0
        assert all(status == RangeStatus.ACTIVE for status in results.values())
        
        # Verify all ranges exist
        all_ranges = orchestrator.list_ranges()
        concurrent_ranges = [r for r in all_ranges if r.range_id.startswith("concurrent-")]
        assert len(concurrent_ranges) == 5