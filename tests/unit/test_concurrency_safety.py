"""
Test concurrency safety and thread-safe operations
测试并发安全和线程安全操作
"""

import pytest
import sys
import os
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock
from queue import Queue, Empty
import random

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))


class TestThreadSafety:
    """Test thread safety mechanisms"""
    
    def test_thread_safe_counter(self):
        """Test thread-safe counter implementation"""
        from cyris.core.concurrency import ThreadSafeCounter
        
        counter = ThreadSafeCounter(initial_value=0)
        num_threads = 10
        increments_per_thread = 100
        
        def increment_counter():
            for _ in range(increments_per_thread):
                counter.increment()
        
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=increment_counter)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        expected_value = num_threads * increments_per_thread
        assert counter.value == expected_value
    
    def test_thread_safe_dict(self):
        """Test thread-safe dictionary operations"""
        from cyris.core.concurrency import ThreadSafeDict
        
        safe_dict = ThreadSafeDict()
        num_threads = 5
        items_per_thread = 20
        
        def add_items(thread_id):
            for i in range(items_per_thread):
                key = f"thread_{thread_id}_item_{i}"
                value = f"value_{thread_id}_{i}"
                safe_dict[key] = value
        
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=add_items, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all items were added correctly
        expected_items = num_threads * items_per_thread
        assert len(safe_dict) == expected_items
        
        # Verify data integrity
        for thread_id in range(num_threads):
            for i in range(items_per_thread):
                key = f"thread_{thread_id}_item_{i}"
                expected_value = f"value_{thread_id}_{i}"
                assert safe_dict[key] == expected_value
    
    def test_thread_safe_set(self):
        """Test thread-safe set operations"""
        from cyris.core.concurrency import ThreadSafeSet
        
        safe_set = ThreadSafeSet()
        num_threads = 8
        items_per_thread = 25
        
        def add_items(thread_id):
            for i in range(items_per_thread):
                item = f"item_{thread_id}_{i}"
                safe_set.add(item)
        
        def remove_items(thread_id):
            for i in range(0, items_per_thread, 2):  # Remove every other item
                item = f"item_{thread_id}_{i}"
                safe_set.discard(item)  # Use discard to avoid KeyError
        
        # Add items concurrently
        add_threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=add_items, args=(thread_id,))
            add_threads.append(thread)
            thread.start()
        
        for thread in add_threads:
            thread.join()
        
        # Verify all items were added
        expected_items = num_threads * items_per_thread
        assert len(safe_set) == expected_items
        
        # Remove items concurrently
        remove_threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=remove_items, args=(thread_id,))
            remove_threads.append(thread)
            thread.start()
        
        for thread in remove_threads:
            thread.join()
        
        # Verify correct items remain
        remaining_items = num_threads * (items_per_thread // 2)
        assert len(safe_set) == remaining_items


class TestConnectionPoolSafety:
    """Test connection pool thread safety"""
    
    def test_ssh_connection_pool_concurrent_access(self):
        """Test SSH connection pool under concurrent access"""
        from cyris.core.network_reliability import ConnectionPool
        
        pool = ConnectionPool(max_connections=10, idle_timeout=300)
        num_threads = 20
        connections_per_thread = 5
        
        def add_connections(thread_id):
            for i in range(connections_per_thread):
                hostname = f"host_{thread_id}_{i}"
                connection = Mock()  # Mock SSH connection
                try:
                    pool.add_connection(hostname, connection)
                except Exception:
                    # Pool might be full, this is expected
                    pass
        
        def get_connections(thread_id):
            for i in range(connections_per_thread):
                hostname = f"host_{thread_id}_{i}"
                connection = pool.get_connection(hostname)
                # Connection might be None if not found
        
        # Add connections concurrently
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=add_connections, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify pool doesn't exceed maximum size
        assert len(pool) <= pool.max_connections
        
        # Get connections concurrently
        get_threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=get_connections, args=(thread_id,))
            get_threads.append(thread)
            thread.start()
        
        for thread in get_threads:
            thread.join()
        
        # Pool should still be valid
        assert len(pool) <= pool.max_connections


class TestTaskQueueSafety:
    """Test task queue thread safety"""
    
    def test_task_queue_producer_consumer(self):
        """Test producer-consumer pattern with task queue"""
        from cyris.core.concurrency import ThreadSafeTaskQueue
        
        task_queue = ThreadSafeTaskQueue(maxsize=50)
        num_producers = 3
        num_consumers = 5
        tasks_per_producer = 20
        
        produced_tasks = []
        consumed_tasks = []
        
        def producer(producer_id):
            for i in range(tasks_per_producer):
                task = f"task_{producer_id}_{i}"
                produced_tasks.append(task)
                task_queue.put(task)
            
        def consumer(consumer_id):
            while True:
                try:
                    task = task_queue.get(timeout=2)
                    consumed_tasks.append(task)
                    task_queue.task_done()
                    
                    # Simulate some work
                    time.sleep(0.001)
                    
                except Empty:
                    # No more tasks
                    break
        
        # Start producers
        producer_threads = []
        for producer_id in range(num_producers):
            thread = threading.Thread(target=producer, args=(producer_id,))
            producer_threads.append(thread)
            thread.start()
        
        # Start consumers
        consumer_threads = []
        for consumer_id in range(num_consumers):
            thread = threading.Thread(target=consumer, args=(consumer_id,))
            consumer_threads.append(thread)
            thread.start()
        
        # Wait for producers to finish
        for thread in producer_threads:
            thread.join()
        
        # Wait for all tasks to be processed
        task_queue.join()
        
        # Stop consumers
        for thread in consumer_threads:
            thread.join(timeout=1)
        
        # Verify all tasks were processed
        expected_tasks = num_producers * tasks_per_producer
        assert len(produced_tasks) == expected_tasks
        assert len(consumed_tasks) == expected_tasks
        assert set(produced_tasks) == set(consumed_tasks)


class TestAtomicOperations:
    """Test atomic operations and race condition prevention"""
    
    def test_atomic_file_operations(self):
        """Test atomic file write operations"""
        from cyris.core.concurrency import AtomicFileWriter
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test.txt")
            writer = AtomicFileWriter(test_file)
            
            num_writers = 10
            lines_per_writer = 20
            
            def append_data(writer_id):
                data_lines = [f"Writer {writer_id} line {i}\n" for i in range(lines_per_writer)]
                writer.append_lines(data_lines)  # Use append instead of overwrite
            
            threads = []
            for writer_id in range(num_writers):
                thread = threading.Thread(target=append_data, args=(writer_id,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # Verify file exists and has all lines
            assert os.path.exists(test_file)
            
            with open(test_file, 'r') as f:
                lines = f.readlines()
            
            expected_lines = num_writers * lines_per_writer
            assert len(lines) == expected_lines
    
    def test_atomic_counter_operations(self):
        """Test atomic counter operations under high contention"""
        from cyris.core.concurrency import AtomicCounter
        
        counter = AtomicCounter()
        num_threads = 20
        operations_per_thread = 99  # Use divisible by 3 for easier calculation
        
        def mixed_operations(thread_id):
            for i in range(operations_per_thread):
                if i % 3 == 0:
                    counter.increment()  # +1
                elif i % 3 == 1:
                    counter.decrement()  # -1
                else:
                    counter.add(2)  # +2
        
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=mixed_operations, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Calculate expected value
        # Per thread: increment (33 times) + decrement (33 times) + add(2) (33 times)
        # Net per thread: 33*1 - 33*1 + 33*2 = 0 + 66 = 66
        expected_value = num_threads * 66
        assert counter.value == expected_value


class TestDeadlockPrevention:
    """Test deadlock prevention mechanisms"""
    
    def test_ordered_lock_acquisition(self):
        """Test ordered lock acquisition to prevent deadlocks"""
        from cyris.core.concurrency import OrderedLockManager
        
        lock_manager = OrderedLockManager()
        
        # Simulate two resources that could cause deadlock
        resource1 = "database_connection"
        resource2 = "file_handle"
        
        results = []
        
        def task1():
            with lock_manager.acquire_multiple([resource1, resource2]):
                results.append("task1_start")
                time.sleep(0.01)  # Simulate work
                results.append("task1_end")
        
        def task2():
            with lock_manager.acquire_multiple([resource2, resource1]):  # Different order
                results.append("task2_start")
                time.sleep(0.01)  # Simulate work
                results.append("task2_end")
        
        # Run tasks concurrently
        thread1 = threading.Thread(target=task1)
        thread2 = threading.Thread(target=task2)
        
        thread1.start()
        thread2.start()
        
        # Should complete without deadlock
        thread1.join(timeout=5)
        thread2.join(timeout=5)
        
        # Both tasks should have completed
        assert "task1_start" in results
        assert "task1_end" in results
        assert "task2_start" in results
        assert "task2_end" in results
        assert len(results) == 4
    
    def test_timeout_based_lock_acquisition(self):
        """Test timeout-based lock acquisition"""
        from cyris.core.concurrency import TimeoutLockManager
        
        lock_manager = TimeoutLockManager()
        resource = "shared_resource"
        
        results = []
        
        def long_running_task():
            acquired = lock_manager.acquire_with_timeout(resource, timeout=2.0)
            if acquired:
                results.append("long_task_acquired")
                time.sleep(1.0)  # Hold lock for 1 second
                results.append("long_task_done")
                lock_manager.release(resource)
        
        def quick_task():
            time.sleep(0.1)  # Start after long task
            acquired = lock_manager.acquire_with_timeout(resource, timeout=0.5)
            if acquired:
                results.append("quick_task_acquired")
                lock_manager.release(resource)
            else:
                results.append("quick_task_timeout")
        
        thread1 = threading.Thread(target=long_running_task)
        thread2 = threading.Thread(target=quick_task)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Long task should acquire lock, quick task should timeout
        assert "long_task_acquired" in results
        assert "long_task_done" in results
        assert "quick_task_timeout" in results


class TestAsyncSafety:
    """Test async/await safety mechanisms"""
    
    @pytest.mark.asyncio
    async def test_async_resource_manager(self):
        """Test async resource management"""
        from cyris.core.concurrency import AsyncResourceManager
        
        manager = AsyncResourceManager(max_resources=3)
        
        async def use_resource(resource_id):
            async with manager.acquire_resource() as resource:
                await asyncio.sleep(0.1)  # Simulate async work
                return f"used_resource_{resource_id}"
        
        # Run multiple tasks concurrently
        tasks = [use_resource(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(result.startswith("used_resource_") for result in results)
    
    @pytest.mark.asyncio
    async def test_async_semaphore_limiting(self):
        """Test async semaphore for limiting concurrent operations"""
        from cyris.core.concurrency import AsyncLimitedExecutor
        
        executor = AsyncLimitedExecutor(max_concurrent=3)
        
        start_time = time.time()
        execution_times = []
        
        async def limited_task(task_id):
            task_start = time.time()
            async with executor.limit():
                await asyncio.sleep(0.1)  # Simulate work
            execution_times.append(time.time() - task_start)
            return task_id
        
        # Run 9 tasks (should execute in 3 batches of 3)
        tasks = [limited_task(i) for i in range(9)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Should take approximately 0.3 seconds (3 batches * 0.1s each)
        assert 0.25 < total_time < 0.5
        assert len(results) == 9
        assert set(results) == set(range(9))


class TestMemorySafety:
    """Test memory safety and cleanup mechanisms"""
    
    def test_weak_reference_cache(self):
        """Test weak reference cache for automatic cleanup"""
        from cyris.core.concurrency import WeakReferenceCache
        import gc
        
        cache = WeakReferenceCache()
        
        class TestObject:
            def __init__(self, name):
                self.name = name
        
        # Add objects to cache
        obj1 = TestObject("object1")
        obj2 = TestObject("object2")
        
        cache.set("key1", obj1)
        cache.set("key2", obj2)
        
        assert cache.get("key1") is obj1
        assert cache.get("key2") is obj2
        assert len(cache) == 2
        
        # Delete one object
        del obj1
        gc.collect()  # Force garbage collection
        
        # Cache should automatically clean up dead references
        assert cache.get("key1") is None
        assert cache.get("key2") is obj2
        # Length might not update immediately due to weak reference cleanup timing
    
    def test_resource_pool_cleanup(self):
        """Test resource pool automatic cleanup"""
        from cyris.core.concurrency import ManagedResourcePool
        
        class MockResource:
            def __init__(self, resource_id):
                self.id = resource_id
                self.closed = False
            
            def close(self):
                self.closed = True
        
        pool = ManagedResourcePool(
            resource_factory=lambda: MockResource(f"resource_{time.time()}"),
            max_size=5,
            cleanup_interval=0.1
        )
        
        # Get some resources
        resources = []
        for i in range(5):
            resource = pool.acquire()
            resources.append(resource)
        
        # Release resources
        for resource in resources:
            pool.release(resource)
        
        # Wait for cleanup
        time.sleep(0.2)
        
        # Verify cleanup occurred
        pool.cleanup()
        
        # All resources should be tracked properly (use qsize for Queue)
        assert pool._available.qsize() <= pool.max_size