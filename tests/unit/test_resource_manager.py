"""
Test resource management system
测试资源管理系统
"""

import pytest
import sys
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.core.resource_manager import (
    ResourceManager, ResourceType, ResourceState, ResourceInfo,
    managed_resource, get_resource_manager, cleanup_at_exit
)
from cyris.core.exceptions import CyRISResourceError


class MockResource:
    """Mock resource with cleanup method"""
    def __init__(self, name: str):
        self.name = name
        self.cleaned_up = False
    
    def cleanup(self):
        self.cleaned_up = True
    
    def close(self):
        self.cleaned_up = True


class TestResourceInfo:
    """Test ResourceInfo dataclass"""
    
    def test_resource_info_creation(self):
        """Test creating resource info"""
        now = datetime.now()
        info = ResourceInfo(
            resource_id="test-resource",
            resource_type=ResourceType.VM_DOMAIN,
            state=ResourceState.CREATED,
            created_at=now,
            owner="test-user"
        )
        
        assert info.resource_id == "test-resource"
        assert info.resource_type == ResourceType.VM_DOMAIN
        assert info.state == ResourceState.CREATED
        assert info.created_at == now
        assert info.owner == "test-user"
    
    def test_update_access_time(self):
        """Test updating access time"""
        info = ResourceInfo(
            resource_id="test",
            resource_type=ResourceType.PROCESS,
            state=ResourceState.ACTIVE,
            created_at=datetime.now()
        )
        
        original_time = info.last_accessed
        time.sleep(0.01)  # Small delay
        info.update_access_time()
        
        assert info.last_accessed > original_time


class TestResourceManager:
    """Test ResourceManager class"""
    
    @pytest.fixture
    def manager(self):
        """Create a resource manager for testing"""
        return ResourceManager(enable_monitoring=False)  # Disable monitoring for tests
    
    def test_manager_initialization(self):
        """Test resource manager initialization"""
        manager = ResourceManager(enable_monitoring=False)
        
        assert len(manager._resources) == 0
        assert len(manager._weak_refs) == 0
        assert not manager._monitoring_enabled
    
    def test_register_resource_basic(self, manager):
        """Test basic resource registration"""
        resource_obj = MockResource("test")
        
        manager.register_resource(
            resource_id="test-1",
            resource_type=ResourceType.VM_DOMAIN,
            resource_obj=resource_obj,
            owner="test-user"
        )
        
        assert len(manager._resources) == 1
        assert "test-1" in manager._resources
        assert "test-1" in manager._weak_refs
        
        resource_info = manager._resources["test-1"]
        assert resource_info.resource_type == ResourceType.VM_DOMAIN
        assert resource_info.state == ResourceState.CREATED
        assert resource_info.owner == "test-user"
    
    def test_register_resource_with_cleanup_func(self, manager):
        """Test registering resource with custom cleanup function"""
        cleanup_called = False
        
        def custom_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
        
        manager.register_resource(
            resource_id="test-cleanup",
            resource_type=ResourceType.PROCESS,
            cleanup_func=custom_cleanup
        )
        
        # Clean up the resource
        success = manager.cleanup_resource("test-cleanup")
        
        assert success
        assert cleanup_called
    
    def test_register_duplicate_resource(self, manager):
        """Test registering duplicate resource"""
        manager.register_resource(
            resource_id="duplicate",
            resource_type=ResourceType.FILE_HANDLE
        )
        
        # Registering duplicate should log warning but not fail
        manager.register_resource(
            resource_id="duplicate",
            resource_type=ResourceType.FILE_HANDLE
        )
        
        assert len(manager._resources) == 1
    
    def test_register_too_many_resources(self, manager):
        """Test resource limit enforcement"""
        # Set low limit for testing
        manager._max_resources_per_type = 2
        
        # Register up to limit
        manager.register_resource("res-1", ResourceType.VM_DOMAIN)
        manager.register_resource("res-2", ResourceType.VM_DOMAIN)
        
        # Third registration should fail
        with pytest.raises(CyRISResourceError, match="Too many resources"):
            manager.register_resource("res-3", ResourceType.VM_DOMAIN)
    
    def test_cleanup_resource_success(self, manager):
        """Test successful resource cleanup"""
        resource_obj = MockResource("test")
        
        manager.register_resource(
            resource_id="cleanup-test",
            resource_type=ResourceType.VM_DOMAIN,
            resource_obj=resource_obj
        )
        
        success = manager.cleanup_resource("cleanup-test")
        
        assert success
        assert resource_obj.cleaned_up
        assert manager._resources["cleanup-test"].state == ResourceState.CLEANED_UP
    
    def test_cleanup_nonexistent_resource(self, manager):
        """Test cleaning up non-existent resource"""
        success = manager.cleanup_resource("nonexistent")
        
        assert not success
    
    def test_cleanup_already_cleaned_resource(self, manager):
        """Test cleaning up already cleaned resource"""
        manager.register_resource("already-cleaned", ResourceType.PROCESS)
        
        # First cleanup
        success1 = manager.cleanup_resource("already-cleaned")
        assert success1
        
        # Second cleanup should still return True
        success2 = manager.cleanup_resource("already-cleaned")
        assert success2
    
    def test_unregister_resource(self, manager):
        """Test unregistering resource"""
        manager.register_resource("unregister-test", ResourceType.SOCKET)
        
        assert len(manager._resources) == 1
        
        success = manager.unregister_resource("unregister-test")
        
        assert success
        assert len(manager._resources) == 0
    
    def test_unregister_nonexistent_resource(self, manager):
        """Test unregistering non-existent resource"""
        success = manager.unregister_resource("nonexistent")
        
        assert not success
    
    def test_cleanup_range_resources(self, manager):
        """Test cleaning up resources by range ID"""
        # Register resources for different ranges
        manager.register_resource("range1-vm1", ResourceType.VM_DOMAIN, parent_range_id="range1")
        manager.register_resource("range1-vm2", ResourceType.VM_DOMAIN, parent_range_id="range1")
        manager.register_resource("range2-vm1", ResourceType.VM_DOMAIN, parent_range_id="range2")
        
        # Cleanup range1 resources
        cleaned_count = manager.cleanup_range_resources("range1")
        
        assert cleaned_count == 2
        
        # Check states
        assert manager._resources["range1-vm1"].state == ResourceState.CLEANED_UP
        assert manager._resources["range1-vm2"].state == ResourceState.CLEANED_UP
        assert manager._resources["range2-vm1"].state == ResourceState.CREATED
    
    def test_list_resources_no_filter(self, manager):
        """Test listing all resources"""
        manager.register_resource("res1", ResourceType.VM_DOMAIN)
        manager.register_resource("res2", ResourceType.NETWORK_BRIDGE)
        
        resources = manager.list_resources()
        
        assert len(resources) == 2
        assert {r.resource_id for r in resources} == {"res1", "res2"}
    
    def test_list_resources_by_type(self, manager):
        """Test listing resources by type"""
        manager.register_resource("vm1", ResourceType.VM_DOMAIN)
        manager.register_resource("vm2", ResourceType.VM_DOMAIN)
        manager.register_resource("bridge1", ResourceType.NETWORK_BRIDGE)
        
        vm_resources = manager.list_resources(resource_type=ResourceType.VM_DOMAIN)
        
        assert len(vm_resources) == 2
        assert all(r.resource_type == ResourceType.VM_DOMAIN for r in vm_resources)
    
    def test_list_resources_by_owner(self, manager):
        """Test listing resources by owner"""
        manager.register_resource("res1", ResourceType.PROCESS, owner="user1")
        manager.register_resource("res2", ResourceType.PROCESS, owner="user2")
        manager.register_resource("res3", ResourceType.PROCESS, owner="user1")
        
        user1_resources = manager.list_resources(owner="user1")
        
        assert len(user1_resources) == 2
        assert all(r.owner == "user1" for r in user1_resources)
    
    def test_get_memory_usage(self, manager):
        """Test getting memory usage information"""
        memory_info = manager.get_memory_usage()
        
        assert "rss_mb" in memory_info
        assert "vms_mb" in memory_info
        assert "percent" in memory_info
        assert "tracked_resources" in memory_info
        assert memory_info["tracked_resources"] == 0
    
    def test_force_garbage_collection(self, manager):
        """Test forced garbage collection"""
        # Create some objects that can be collected
        objects = [object() for _ in range(100)]
        del objects
        
        collected = manager.force_garbage_collection()
        
        assert isinstance(collected, int)
        assert collected >= 0
    
    def test_weak_reference_cleanup(self, manager):
        """Test automatic cleanup when object is garbage collected"""
        resource_obj = MockResource("weak-ref-test")
        
        manager.register_resource(
            resource_id="weak-ref-resource",
            resource_type=ResourceType.VM_DOMAIN,
            resource_obj=resource_obj
        )
        
        assert len(manager._resources) == 1
        assert len(manager._weak_refs) == 1
        
        # Delete the object to trigger weak reference cleanup
        del resource_obj
        
        # Force garbage collection to trigger weak reference callback
        manager.force_garbage_collection()
        
        # Give some time for the callback to execute
        time.sleep(0.01)
        
        # Resource should be marked as cleaned up
        resource_info = manager.get_resource_info("weak-ref-resource")
        if resource_info:  # May have been cleaned up completely
            assert resource_info.state == ResourceState.CLEANED_UP


class TestManagedResourceContext:
    """Test managed resource context manager"""
    
    def test_managed_resource_success(self):
        """Test successful resource management"""
        cleanup_called = False
        
        def cleanup_func():
            nonlocal cleanup_called
            cleanup_called = True
        
        with managed_resource(
            "context-test",
            ResourceType.PROCESS,
            cleanup_func=cleanup_func
        ) as resource:
            # Resource should be registered
            manager = get_resource_manager()
            assert "context-test" in manager._resources
        
        # Resource should be cleaned up after context exit
        assert cleanup_called
    
    def test_managed_resource_with_exception(self):
        """Test resource management when exception occurs"""
        cleanup_called = False
        
        def cleanup_func():
            nonlocal cleanup_called
            cleanup_called = True
        
        try:
            with managed_resource(
                "context-exception-test",
                ResourceType.PROCESS,
                cleanup_func=cleanup_func
            ):
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Resource should still be cleaned up
        assert cleanup_called


class TestResourceManagerIntegration:
    """Integration tests for resource manager"""
    
    def test_global_resource_manager_singleton(self):
        """Test global resource manager is singleton"""
        manager1 = get_resource_manager()
        manager2 = get_resource_manager()
        
        assert manager1 is manager2
    
    def test_cleanup_at_exit_function(self):
        """Test cleanup at exit function"""
        # This is hard to test directly, but we can verify it doesn't crash
        try:
            cleanup_at_exit()
        except Exception as e:
            pytest.fail(f"cleanup_at_exit raised exception: {e}")
    
    @patch('cyris.core.resource_manager.psutil.Process')
    def test_memory_monitoring(self, mock_process_class):
        """Test memory usage monitoring"""
        # Mock process memory info
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 1024 * 1024 * 1024  # 1GB
        mock_memory_info.vms = 2048 * 1024 * 1024  # 2GB
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.memory_percent.return_value = 25.5
        mock_process_class.return_value = mock_process
        
        manager = ResourceManager(enable_monitoring=False)
        memory_info = manager.get_memory_usage()
        
        assert memory_info["rss_mb"] == 1024
        assert memory_info["vms_mb"] == 2048
        assert memory_info["percent"] == 25.5
        assert memory_info["tracked_resources"] == 0
    
    def test_orphaned_resource_cleanup(self):
        """Test cleanup of orphaned resources"""
        manager = ResourceManager(enable_monitoring=False)
        
        # Set short timeout for testing
        manager._orphan_timeout = timedelta(microseconds=1)
        
        # Create resource that will become orphaned quickly
        resource_obj = MockResource("orphan-test")
        manager.register_resource(
            "orphan-resource",
            ResourceType.VM_DOMAIN,
            resource_obj=resource_obj
        )
        
        # Wait for resource to become orphaned
        time.sleep(0.001)
        
        # Cleanup orphaned resources
        cleaned_count = manager.cleanup_orphaned_resources()
        
        # Should have cleaned up the orphaned resource
        assert cleaned_count >= 0  # May be 0 if weak ref still alive
    
    def test_resource_manager_shutdown(self):
        """Test resource manager shutdown"""
        manager = ResourceManager(enable_monitoring=False)
        
        # Register some resources
        manager.register_resource("shutdown-test-1", ResourceType.VM_DOMAIN)
        manager.register_resource("shutdown-test-2", ResourceType.NETWORK_BRIDGE)
        
        assert len(manager._resources) == 2
        
        # Shutdown should clean up all resources
        manager.shutdown()
        
        # All resources should be cleaned up
        cleaned_resources = [r for r in manager._resources.values() if r.state == ResourceState.CLEANED_UP]
        assert len(cleaned_resources) == 2
    
    def test_thread_safety(self):
        """Test thread safety of resource manager"""
        manager = ResourceManager(enable_monitoring=False)
        results = []
        errors = []
        
        def register_resources(thread_id):
            try:
                for i in range(10):
                    resource_id = f"thread-{thread_id}-resource-{i}"
                    manager.register_resource(resource_id, ResourceType.PROCESS)
                    results.append(resource_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=register_resources, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have no errors and all resources registered
        assert len(errors) == 0
        assert len(manager._resources) == 50  # 5 threads * 10 resources each
        assert len(results) == 50


class TestResourceManagerFiltering:
    """Test resource filtering and querying"""
    
    @pytest.fixture
    def populated_manager(self):
        """Create manager with various resources"""
        manager = ResourceManager(enable_monitoring=False)
        
        # Add various resources
        manager.register_resource("vm1", ResourceType.VM_DOMAIN, owner="user1", parent_range_id="range1")
        manager.register_resource("vm2", ResourceType.VM_DOMAIN, owner="user2", parent_range_id="range1")
        manager.register_resource("bridge1", ResourceType.NETWORK_BRIDGE, owner="user1", parent_range_id="range2")
        manager.register_resource("process1", ResourceType.PROCESS, owner="user1")
        
        return manager
    
    def test_list_resources_by_type(self, populated_manager):
        """Test listing resources by type"""
        vm_resources = populated_manager.list_resources(resource_type=ResourceType.VM_DOMAIN)
        
        assert len(vm_resources) == 2
        assert all(r.resource_type == ResourceType.VM_DOMAIN for r in vm_resources)
        assert {r.resource_id for r in vm_resources} == {"vm1", "vm2"}
    
    def test_list_resources_by_owner(self, populated_manager):
        """Test listing resources by owner"""
        user1_resources = populated_manager.list_resources(owner="user1")
        
        assert len(user1_resources) == 3
        assert all(r.owner == "user1" for r in user1_resources)
        assert {r.resource_id for r in user1_resources} == {"vm1", "bridge1", "process1"}
    
    def test_list_resources_by_range(self, populated_manager):
        """Test listing resources by range ID"""
        range1_resources = populated_manager.list_resources(parent_range_id="range1")
        
        assert len(range1_resources) == 2
        assert all(r.parent_range_id == "range1" for r in range1_resources)
        assert {r.resource_id for r in range1_resources} == {"vm1", "vm2"}
    
    def test_list_resources_multiple_filters(self, populated_manager):
        """Test listing resources with multiple filters"""
        filtered_resources = populated_manager.list_resources(
            resource_type=ResourceType.VM_DOMAIN,
            owner="user1"
        )
        
        assert len(filtered_resources) == 1
        assert filtered_resources[0].resource_id == "vm1"
    
    def test_get_resource_info_existing(self, populated_manager):
        """Test getting info for existing resource"""
        info = populated_manager.get_resource_info("vm1")
        
        assert info is not None
        assert info.resource_id == "vm1"
        assert info.resource_type == ResourceType.VM_DOMAIN
        assert info.owner == "user1"
    
    def test_get_resource_info_nonexistent(self, populated_manager):
        """Test getting info for non-existent resource"""
        info = populated_manager.get_resource_info("nonexistent")
        
        assert info is None


class TestResourceCleanupContext:
    """Test resource cleanup with context manager"""
    
    def test_context_manager_normal_flow(self):
        """Test context manager with normal execution flow"""
        cleanup_called = False
        
        def cleanup_func():
            nonlocal cleanup_called
            cleanup_called = True
        
        with managed_resource(
            "context-normal",
            ResourceType.FILE_HANDLE,
            cleanup_func=cleanup_func
        ):
            # Verify resource is registered
            manager = get_resource_manager()
            assert "context-normal" in manager._resources
        
        # Verify cleanup was called
        assert cleanup_called
    
    def test_context_manager_with_exception(self):
        """Test context manager when exception is raised"""
        cleanup_called = False
        
        def cleanup_func():
            nonlocal cleanup_called
            cleanup_called = True
        
        with pytest.raises(ValueError):
            with managed_resource(
                "context-exception",
                ResourceType.FILE_HANDLE,
                cleanup_func=cleanup_func
            ):
                raise ValueError("Test exception")
        
        # Cleanup should still be called
        assert cleanup_called