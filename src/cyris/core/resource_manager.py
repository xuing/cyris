"""
Resource Management System for CyRIS

This module provides centralized resource tracking, cleanup, and memory management
to prevent resource leaks and ensure proper cleanup of cyber range components.
"""

import gc
import logging
import threading
import weakref

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
from typing import Dict, List, Set, Optional, Any, Protocol, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
from enum import Enum

from .exceptions import CyRISResourceError, CyRISException, handle_exception


logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources managed by CyRIS"""
    VM_DOMAIN = "vm_domain"
    NETWORK_BRIDGE = "network_bridge" 
    NETWORK_INTERFACE = "network_interface"
    PROCESS = "process"
    FILE_HANDLE = "file_handle"
    SOCKET = "socket"
    TEMPORARY_FILE = "temporary_file"
    LIBVIRT_CONNECTION = "libvirt_connection"
    SSH_CONNECTION = "ssh_connection"


class ResourceState(Enum):
    """States of managed resources"""
    CREATED = "created"
    ACTIVE = "active"
    CLEANUP_REQUESTED = "cleanup_requested"
    CLEANED_UP = "cleaned_up"
    ERROR = "error"


@dataclass
class ResourceInfo:
    """Information about a managed resource"""
    resource_id: str
    resource_type: ResourceType
    state: ResourceState
    created_at: datetime
    last_accessed: datetime = field(default_factory=datetime.now)
    cleanup_func: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    owner: Optional[str] = None
    parent_range_id: Optional[str] = None
    
    def update_access_time(self):
        """Update last accessed time"""
        self.last_accessed = datetime.now()


class ResourceCleanupProtocol(Protocol):
    """Protocol for resources that can clean themselves up"""
    
    def cleanup(self) -> None:
        """Clean up the resource"""
        ...


class ResourceManager:
    """
    Central resource manager for tracking and cleaning up CyRIS resources.
    
    This manager helps prevent resource leaks by:
    - Tracking all allocated resources
    - Providing automatic cleanup on shutdown
    - Detecting and cleaning up orphaned resources
    - Monitoring memory and resource usage
    - Supporting custom cleanup functions
    """
    
    def __init__(self, enable_monitoring: bool = True):
        """
        Initialize the resource manager.
        
        Args:
            enable_monitoring: Whether to enable resource usage monitoring
        """
        self._resources: Dict[str, ResourceInfo] = {}
        self._weak_refs: Dict[str, weakref.ref] = {}
        self._cleanup_functions: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._shutdown_requested = threading.Event()
        self._monitoring_enabled = enable_monitoring
        self._monitoring_thread: Optional[threading.Thread] = None
        
        # Memory usage tracking
        self._memory_threshold_mb = 1024  # 1GB default threshold
        self._max_resources_per_type = 100
        
        # Cleanup settings
        self._orphan_timeout = timedelta(hours=1)
        self._cleanup_interval = timedelta(minutes=5)
        
        if enable_monitoring:
            self._start_monitoring()
        
        logger.info("ResourceManager initialized")
    
    def register_resource(
        self,
        resource_id: str,
        resource_type: ResourceType,
        resource_obj: Any = None,
        cleanup_func: Optional[Callable] = None,
        owner: Optional[str] = None,
        parent_range_id: Optional[str] = None,
        **metadata
    ) -> None:
        """
        Register a resource for tracking and cleanup.
        
        Args:
            resource_id: Unique identifier for the resource
            resource_type: Type of resource
            resource_obj: The actual resource object (for weak references)
            cleanup_func: Function to call for cleanup
            owner: Owner of the resource (user, service, etc.)
            parent_range_id: ID of cyber range this resource belongs to
            **metadata: Additional metadata about the resource
        """
        try:
            with self._lock:
                if resource_id in self._resources:
                    logger.warning(f"Resource {resource_id} already registered")
                    return
                
                # Check resource limits
                type_count = sum(1 for r in self._resources.values() if r.resource_type == resource_type)
                if type_count >= self._max_resources_per_type:
                    raise CyRISResourceError(
                        f"Too many resources of type {resource_type.value} (limit: {self._max_resources_per_type})",
                        operation="register_resource",
                        additional_data={"resource_type": resource_type.value, "count": type_count}
                    )
                
                # Create resource info
                resource_info = ResourceInfo(
                    resource_id=resource_id,
                    resource_type=resource_type,
                    state=ResourceState.CREATED,
                    created_at=datetime.now(),
                    cleanup_func=cleanup_func,
                    metadata=metadata,
                    owner=owner,
                    parent_range_id=parent_range_id
                )
                
                self._resources[resource_id] = resource_info
                
                # Create weak reference if object provided
                if resource_obj is not None:
                    self._weak_refs[resource_id] = weakref.ref(
                        resource_obj,
                        lambda ref: self._handle_weak_ref_cleanup(resource_id)
                    )
                
                logger.debug(f"Registered resource {resource_id} of type {resource_type.value}")
                
        except Exception as e:
            handle_exception(
                e,
                context={
                    "operation": "register_resource",
                    "resource_id": resource_id,
                    "resource_type": resource_type.value
                }
            )
            raise
    
    def unregister_resource(self, resource_id: str) -> bool:
        """
        Unregister a resource from tracking.
        
        Args:
            resource_id: ID of resource to unregister
            
        Returns:
            True if resource was found and unregistered, False otherwise
        """
        with self._lock:
            if resource_id not in self._resources:
                return False
            
            # Update state
            self._resources[resource_id].state = ResourceState.CLEANED_UP
            
            # Remove from tracking
            del self._resources[resource_id]
            self._weak_refs.pop(resource_id, None)
            self._cleanup_functions.pop(resource_id, None)
            
            logger.debug(f"Unregistered resource {resource_id}")
            return True
    
    def cleanup_resource(self, resource_id: str) -> bool:
        """
        Clean up a specific resource.
        
        Args:
            resource_id: ID of resource to clean up
            
        Returns:
            True if cleanup succeeded, False otherwise
        """
        try:
            with self._lock:
                if resource_id not in self._resources:
                    logger.warning(f"Resource {resource_id} not found for cleanup")
                    return False
                
                resource_info = self._resources[resource_id]
                
                if resource_info.state == ResourceState.CLEANED_UP:
                    logger.debug(f"Resource {resource_id} already cleaned up")
                    return True
                
                # Mark as cleanup requested
                resource_info.state = ResourceState.CLEANUP_REQUESTED
                
                success = False
                error_messages = []
                
                # Try cleanup function first
                if resource_info.cleanup_func:
                    try:
                        resource_info.cleanup_func()
                        success = True
                        logger.debug(f"Cleaned up resource {resource_id} using custom cleanup function")
                    except Exception as e:
                        error_messages.append(f"Custom cleanup failed: {e}")
                        logger.error(f"Custom cleanup failed for {resource_id}: {e}")
                
                # Try weak reference cleanup
                if not success and resource_id in self._weak_refs:
                    weak_ref = self._weak_refs[resource_id]
                    obj = weak_ref()
                    if obj is not None:
                        try:
                            if hasattr(obj, 'cleanup'):
                                obj.cleanup()
                            elif hasattr(obj, 'close'):
                                obj.close()
                            elif hasattr(obj, 'destroy'):
                                obj.destroy()
                            else:
                                logger.debug(f"Resource {resource_id} object has no cleanup method")
                            success = True
                            logger.debug(f"Cleaned up resource {resource_id} using object method")
                        except Exception as e:
                            error_messages.append(f"Object cleanup failed: {e}")
                            logger.error(f"Object cleanup failed for {resource_id}: {e}")
                    else:
                        # Weak reference is dead, consider it cleaned up
                        success = True
                        logger.debug(f"Resource {resource_id} object was garbage collected")
                
                # If no cleanup method available, consider it successful
                # (resource might be a simple tracking entry)
                if not success and not resource_info.cleanup_func and resource_id not in self._weak_refs:
                    success = True
                    logger.debug(f"Resource {resource_id} has no cleanup method, marking as cleaned up")
                
                # Update state
                if success:
                    resource_info.state = ResourceState.CLEANED_UP
                    logger.info(f"Successfully cleaned up resource {resource_id}")
                else:
                    resource_info.state = ResourceState.ERROR
                    error_msg = "; ".join(error_messages)
                    logger.error(f"Failed to clean up resource {resource_id}: {error_msg}")
                
                return success
                
        except Exception as e:
            handle_exception(
                e,
                context={
                    "operation": "cleanup_resource",
                    "resource_id": resource_id
                }
            )
            return False
    
    def cleanup_range_resources(self, range_id: str) -> int:
        """
        Clean up all resources belonging to a specific cyber range.
        
        Args:
            range_id: ID of the cyber range
            
        Returns:
            Number of resources successfully cleaned up
        """
        cleaned_count = 0
        
        with self._lock:
            range_resources = [
                resource_id for resource_id, resource_info in self._resources.items()
                if resource_info.parent_range_id == range_id
            ]
        
        for resource_id in range_resources:
            if self.cleanup_resource(resource_id):
                cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} resources for range {range_id}")
        return cleaned_count
    
    def cleanup_orphaned_resources(self) -> int:
        """
        Clean up resources that have been orphaned (weak references are None).
        
        Returns:
            Number of resources cleaned up
        """
        cleaned_count = 0
        orphaned_resources = []
        
        with self._lock:
            current_time = datetime.now()
            
            for resource_id, resource_info in self._resources.items():
                # Check if resource is old enough to be considered orphaned
                if current_time - resource_info.created_at < self._orphan_timeout:
                    continue
                
                # Check if weak reference is dead
                weak_ref = self._weak_refs.get(resource_id)
                if weak_ref is not None and weak_ref() is None:
                    orphaned_resources.append(resource_id)
                    continue
                
                # Check if resource hasn't been accessed recently
                if current_time - resource_info.last_accessed > self._orphan_timeout * 2:
                    orphaned_resources.append(resource_id)
        
        # Clean up orphaned resources
        for resource_id in orphaned_resources:
            if self.cleanup_resource(resource_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} orphaned resources")
        
        return cleaned_count
    
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """Get information about a resource"""
        with self._lock:
            return self._resources.get(resource_id)
    
    def list_resources(
        self,
        resource_type: Optional[ResourceType] = None,
        owner: Optional[str] = None,
        parent_range_id: Optional[str] = None,
        state: Optional[ResourceState] = None
    ) -> List[ResourceInfo]:
        """
        List resources with optional filtering.
        
        Args:
            resource_type: Filter by resource type
            owner: Filter by owner
            parent_range_id: Filter by parent range ID
            state: Filter by state
            
        Returns:
            List of matching resource information
        """
        with self._lock:
            resources = list(self._resources.values())
            
            if resource_type:
                resources = [r for r in resources if r.resource_type == resource_type]
            if owner:
                resources = [r for r in resources if r.owner == owner]
            if parent_range_id:
                resources = [r for r in resources if r.parent_range_id == parent_range_id]
            if state:
                resources = [r for r in resources if r.state == state]
            
            return resources
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage information"""
        try:
            if not PSUTIL_AVAILABLE:
                return {
                    "rss_mb": 0.0,
                    "vms_mb": 0.0,
                    "available": False,
                    "message": "psutil not available"
                }
            
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": process.memory_percent(),
                "tracked_resources": len(self._resources),
                "weak_refs": len(self._weak_refs)
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {}
    
    def force_garbage_collection(self) -> int:
        """Force garbage collection and return number of objects collected"""
        try:
            collected = gc.collect()
            logger.debug(f"Garbage collection freed {collected} objects")
            return collected
        except Exception as e:
            logger.error(f"Garbage collection failed: {e}")
            return 0
    
    def shutdown(self) -> None:
        """Shutdown the resource manager and clean up all resources"""
        logger.info("Shutting down ResourceManager")
        
        self._shutdown_requested.set()
        
        # Stop monitoring thread
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)
        
        # Clean up all resources
        with self._lock:
            resource_ids = list(self._resources.keys())
        
        cleaned_count = 0
        for resource_id in resource_ids:
            if self.cleanup_resource(resource_id):
                cleaned_count += 1
        
        logger.info(f"ResourceManager shutdown complete, cleaned up {cleaned_count} resources")
    
    def _handle_weak_ref_cleanup(self, resource_id: str) -> None:
        """Handle cleanup when weak reference is garbage collected"""
        logger.debug(f"Weak reference cleanup triggered for resource {resource_id}")
        self.cleanup_resource(resource_id)
    
    def _start_monitoring(self) -> None:
        """Start the resource monitoring thread"""
        def monitor():
            while not self._shutdown_requested.wait(self._cleanup_interval.total_seconds()):
                try:
                    # Check memory usage
                    memory_info = self.get_memory_usage()
                    if memory_info.get("rss_mb", 0) > self._memory_threshold_mb:
                        logger.warning(f"High memory usage: {memory_info['rss_mb']:.1f}MB")
                        
                        # Try cleanup and garbage collection
                        self.cleanup_orphaned_resources()
                        self.force_garbage_collection()
                    
                    # Regular orphan cleanup
                    self.cleanup_orphaned_resources()
                    
                except Exception as e:
                    logger.error(f"Resource monitoring error: {e}")
        
        self._monitoring_thread = threading.Thread(target=monitor, daemon=True, name="ResourceMonitor")
        self._monitoring_thread.start()
        logger.debug("Resource monitoring started")


# Global resource manager instance
_global_resource_manager: Optional[ResourceManager] = None
_manager_lock = threading.Lock()


def get_resource_manager() -> ResourceManager:
    """Get or create the global resource manager instance"""
    global _global_resource_manager
    
    with _manager_lock:
        if _global_resource_manager is None:
            _global_resource_manager = ResourceManager()
        return _global_resource_manager


@contextmanager
def managed_resource(
    resource_id: str,
    resource_type: ResourceType,
    resource_obj: Any = None,
    cleanup_func: Optional[Callable] = None,
    **metadata
):
    """
    Context manager for automatically managing a resource.
    
    Args:
        resource_id: Unique identifier for the resource
        resource_type: Type of resource
        resource_obj: The actual resource object
        cleanup_func: Function to call for cleanup
        **metadata: Additional metadata
    
    Example:
        with managed_resource("vm-123", ResourceType.VM_DOMAIN, vm_domain, cleanup_func=destroy_vm):
            # Use the resource
            pass
        # Resource is automatically cleaned up
    """
    manager = get_resource_manager()
    
    try:
        manager.register_resource(
            resource_id=resource_id,
            resource_type=resource_type,
            resource_obj=resource_obj,
            cleanup_func=cleanup_func,
            **metadata
        )
        yield resource_obj
    finally:
        manager.cleanup_resource(resource_id)
        manager.unregister_resource(resource_id)


def cleanup_at_exit():
    """Cleanup function to be called at program exit"""
    global _global_resource_manager
    if _global_resource_manager:
        _global_resource_manager.shutdown()


# Register cleanup at exit
import atexit
atexit.register(cleanup_at_exit)