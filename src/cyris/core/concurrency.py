"""
Concurrency and Thread Safety

This module provides thread-safe data structures and concurrency utilities
for safe multi-threaded operations in the CyRIS system.

Follows KISS principle with simple, focused implementations.
"""

import threading
import asyncio
import time
import os
import tempfile
import weakref
from typing import Any, Dict, List, Optional, Set, Union, Callable, AsyncGenerator
from contextlib import contextmanager, asynccontextmanager
from queue import Queue, Empty, Full
from collections import defaultdict
import logging


logger = logging.getLogger(__name__)


class ThreadSafeCounter:
    """Thread-safe counter with atomic operations"""
    
    def __init__(self, initial_value: int = 0):
        """Initialize counter with optional initial value"""
        self._value = initial_value
        self._lock = threading.Lock()
    
    def increment(self, amount: int = 1) -> int:
        """Atomically increment counter and return new value"""
        with self._lock:
            self._value += amount
            return self._value
    
    def decrement(self, amount: int = 1) -> int:
        """Atomically decrement counter and return new value"""
        with self._lock:
            self._value -= amount
            return self._value
    
    def reset(self, value: int = 0) -> int:
        """Atomically reset counter to value and return old value"""
        with self._lock:
            old_value = self._value
            self._value = value
            return old_value
    
    @property
    def value(self) -> int:
        """Get current counter value (thread-safe read)"""
        with self._lock:
            return self._value


class ThreadSafeDict(Dict[Any, Any]):
    """Thread-safe dictionary with atomic operations"""
    
    def __init__(self, *args, **kwargs):
        """Initialize thread-safe dictionary"""
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()  # Reentrant lock for nested operations
    
    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)
    
    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)
    
    def __len__(self):
        with self._lock:
            return super().__len__()
    
    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)
    
    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)
    
    def pop(self, key, *args):
        with self._lock:
            return super().pop(key, *args)
    
    def update(self, *args, **kwargs):
        with self._lock:
            super().update(*args, **kwargs)
    
    def clear(self):
        with self._lock:
            super().clear()
    
    def keys(self):
        with self._lock:
            return list(super().keys())
    
    def values(self):
        with self._lock:
            return list(super().values())
    
    def items(self):
        with self._lock:
            return list(super().items())


class ThreadSafeSet(Set[Any]):
    """Thread-safe set with atomic operations"""
    
    def __init__(self, *args):
        """Initialize thread-safe set"""
        self._data = set(*args)
        self._lock = threading.RLock()
    
    def add(self, item):
        with self._lock:
            self._data.add(item)
    
    def discard(self, item):
        with self._lock:
            self._data.discard(item)
    
    def remove(self, item):
        with self._lock:
            self._data.remove(item)
    
    def pop(self):
        with self._lock:
            return self._data.pop()
    
    def clear(self):
        with self._lock:
            self._data.clear()
    
    def __len__(self):
        with self._lock:
            return len(self._data)
    
    def __contains__(self, item):
        with self._lock:
            return item in self._data
    
    def __iter__(self):
        with self._lock:
            return iter(list(self._data))  # Return snapshot
    
    def copy(self):
        with self._lock:
            return ThreadSafeSet(self._data.copy())
    
    def union(self, other):
        with self._lock:
            return self._data.union(other)
    
    def intersection(self, other):
        with self._lock:
            return self._data.intersection(other)


class ThreadSafeTaskQueue:
    """Thread-safe task queue for producer-consumer patterns"""
    
    def __init__(self, maxsize: int = 0):
        """Initialize task queue with optional size limit"""
        self._queue = Queue(maxsize=maxsize)
    
    def put(self, item, block: bool = True, timeout: Optional[float] = None):
        """Put item in queue"""
        self._queue.put(item, block, timeout)
    
    def get(self, block: bool = True, timeout: Optional[float] = None):
        """Get item from queue"""
        return self._queue.get(block, timeout)
    
    def task_done(self):
        """Mark task as done"""
        self._queue.task_done()
    
    def join(self):
        """Wait for all tasks to complete"""
        self._queue.join()
    
    def qsize(self):
        """Get approximate queue size"""
        return self._queue.qsize()
    
    def empty(self):
        """Check if queue is empty"""
        return self._queue.empty()
    
    def full(self):
        """Check if queue is full"""
        return self._queue.full()


class AtomicFileWriter:
    """Atomic file operations to prevent corruption"""
    
    def __init__(self, filename: str):
        """Initialize atomic file writer"""
        self.filename = filename
        self._lock = threading.Lock()
    
    def write_lines(self, lines: List[str]):
        """Atomically write lines to file"""
        with self._lock:
            # Write to temporary file first
            temp_fd, temp_path = tempfile.mkstemp(
                prefix=f"{os.path.basename(self.filename)}_",
                dir=os.path.dirname(self.filename) or "."
            )
            
            try:
                with os.fdopen(temp_fd, 'w') as temp_file:
                    temp_file.writelines(lines)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())  # Force write to disk
                
                # Atomic move (rename) to final location
                os.replace(temp_path, self.filename)
                
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise
    
    def append_lines(self, lines: List[str]):
        """Atomically append lines to file"""
        with self._lock:
            existing_lines = []
            
            # Read existing content if file exists
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    existing_lines = f.readlines()
            
            # Write all content atomically
            all_lines = existing_lines + lines
            self.write_lines(all_lines)


class AtomicCounter:
    """High-performance atomic counter using threading primitives"""
    
    def __init__(self, initial_value: int = 0):
        """Initialize atomic counter"""
        self._value = initial_value
        self._lock = threading.Lock()
    
    def increment(self, amount: int = 1) -> int:
        """Atomically increment and return new value"""
        with self._lock:
            self._value += amount
            return self._value
    
    def decrement(self, amount: int = 1) -> int:
        """Atomically decrement and return new value"""
        with self._lock:
            self._value -= amount
            return self._value
    
    def add(self, amount: int) -> int:
        """Atomically add amount and return new value"""
        with self._lock:
            self._value += amount
            return self._value
    
    def get_and_set(self, new_value: int) -> int:
        """Atomically get current value and set new value"""
        with self._lock:
            old_value = self._value
            self._value = new_value
            return old_value
    
    @property
    def value(self) -> int:
        """Get current value (thread-safe)"""
        with self._lock:
            return self._value


class OrderedLockManager:
    """Manages locks in consistent order to prevent deadlocks"""
    
    def __init__(self):
        """Initialize ordered lock manager"""
        self._locks = defaultdict(threading.RLock)
        self._global_lock = threading.Lock()
    
    @contextmanager
    def acquire_multiple(self, resource_names: List[str]):
        """Acquire multiple locks in consistent order"""
        # Sort names to ensure consistent ordering
        sorted_names = sorted(set(resource_names))
        acquired_locks = []
        
        try:
            for name in sorted_names:
                lock = self._get_lock(name)
                lock.acquire()
                acquired_locks.append(lock)
            
            yield
            
        finally:
            # Release in reverse order
            for lock in reversed(acquired_locks):
                try:
                    lock.release()
                except:
                    pass  # Ignore errors during cleanup
    
    def _get_lock(self, resource_name: str) -> threading.RLock:
        """Get or create lock for resource"""
        # Use global lock to prevent race condition in lock creation
        with self._global_lock:
            return self._locks[resource_name]


class TimeoutLockManager:
    """Lock manager with timeout support"""
    
    def __init__(self):
        """Initialize timeout lock manager"""
        self._locks = defaultdict(threading.Lock)
        self._global_lock = threading.Lock()
    
    def acquire_with_timeout(self, resource_name: str, timeout: float) -> bool:
        """Try to acquire lock with timeout"""
        lock = self._get_lock(resource_name)
        return lock.acquire(timeout=timeout)
    
    def release(self, resource_name: str):
        """Release lock for resource"""
        lock = self._get_lock(resource_name)
        try:
            lock.release()
        except:
            pass  # Lock might not be held by current thread
    
    def _get_lock(self, resource_name: str) -> threading.Lock:
        """Get or create lock for resource"""
        with self._global_lock:
            return self._locks[resource_name]


class AsyncResourceManager:
    """Async resource manager with semaphore limiting"""
    
    def __init__(self, max_resources: int = 10):
        """Initialize async resource manager"""
        self.max_resources = max_resources
        self._semaphore = asyncio.Semaphore(max_resources)
        self._resource_counter = AtomicCounter()
    
    @asynccontextmanager
    async def acquire_resource(self):
        """Acquire a resource with async context manager"""
        async with self._semaphore:
            resource_id = self._resource_counter.increment()
            try:
                yield f"resource_{resource_id}"
            finally:
                pass  # Resource cleanup would go here


class AsyncLimitedExecutor:
    """Async executor with concurrency limiting"""
    
    def __init__(self, max_concurrent: int = 5):
        """Initialize limited async executor"""
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    @asynccontextmanager
    async def limit(self):
        """Limit concurrent execution"""
        async with self._semaphore:
            yield


class WeakReferenceCache:
    """Cache with automatic cleanup using weak references"""
    
    def __init__(self):
        """Initialize weak reference cache"""
        self._cache = {}
        self._lock = threading.RLock()
    
    def set(self, key: str, obj: Any):
        """Store object with weak reference"""
        def cleanup(ref):
            with self._lock:
                if key in self._cache and self._cache[key] is ref:
                    del self._cache[key]
        
        with self._lock:
            self._cache[key] = weakref.ref(obj, cleanup)
    
    def get(self, key: str) -> Optional[Any]:
        """Get object from cache"""
        with self._lock:
            weak_ref = self._cache.get(key)
            if weak_ref is not None:
                obj = weak_ref()
                if obj is not None:
                    return obj
                else:
                    # Clean up dead reference
                    del self._cache[key]
            return None
    
    def __len__(self):
        """Get cache size"""
        with self._lock:
            # Clean up dead references
            dead_keys = []
            for key, weak_ref in self._cache.items():
                if weak_ref() is None:
                    dead_keys.append(key)
            
            for key in dead_keys:
                del self._cache[key]
            
            return len(self._cache)


class ManagedResourcePool:
    """Resource pool with automatic lifecycle management"""
    
    def __init__(
        self, 
        resource_factory: Callable[[], Any],
        max_size: int = 10,
        cleanup_interval: float = 60.0
    ):
        """Initialize managed resource pool"""
        self.resource_factory = resource_factory
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        
        self._available = Queue(maxsize=max_size)
        self._in_use = ThreadSafeSet()
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
    
    def acquire(self) -> Any:
        """Acquire resource from pool"""
        with self._lock:
            try:
                # Try to get existing resource
                resource = self._available.get_nowait()
            except Empty:
                # Create new resource
                resource = self.resource_factory()
            
            self._in_use.add(resource)
            return resource
    
    def release(self, resource: Any):
        """Release resource back to pool"""
        with self._lock:
            if resource in self._in_use:
                self._in_use.discard(resource)
                
                try:
                    # Return to available pool if not full
                    self._available.put_nowait(resource)
                except Full:
                    # Pool is full, close resource
                    if hasattr(resource, 'close'):
                        resource.close()
    
    def cleanup(self):
        """Clean up old or unused resources"""
        current_time = time.time()
        
        with self._lock:
            if current_time - self._last_cleanup < self.cleanup_interval:
                return
            
            # Clean up available resources that might be stale
            cleaned_resources = []
            
            try:
                while True:
                    resource = self._available.get_nowait()
                    cleaned_resources.append(resource)
            except Empty:
                pass
            
            # Put back valid resources (in real implementation,
            # you might check resource validity here)
            for resource in cleaned_resources:
                try:
                    self._available.put_nowait(resource)
                except Full:
                    if hasattr(resource, 'close'):
                        resource.close()
            
            self._last_cleanup = current_time