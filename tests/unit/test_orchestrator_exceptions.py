"""
Test orchestrator with unified exception handling
测试编排器的统一异常处理
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.config.settings import CyRISSettings
from cyris.services.orchestrator import RangeOrchestrator, RangeMetadata, RangeStatus
from cyris.core.exceptions import (
    CyRISVirtualizationError, CyRISNetworkError, CyRISException,
    CyRISErrorCode
)


class MockHost:
    """Mock host for testing"""
    def __init__(self, host_id="test-host", name="Test Host"):
        self.id = host_id
        self.host_id = host_id
        self.name = name


class MockGuest:
    """Mock guest for testing"""
    def __init__(self, guest_id="test-guest", name="Test Guest", ip_addr=None, tasks=None):
        self.id = guest_id
        self.guest_id = guest_id
        self.name = name
        self.ip_addr = ip_addr
        self.tasks = tasks or []


class MockProvider:
    """Mock infrastructure provider"""
    def __init__(self, fail_hosts=False, fail_guests=False):
        self.fail_hosts = fail_hosts
        self.fail_guests = fail_guests
        self._connection = Mock()
    
    def create_hosts(self, hosts):
        if self.fail_hosts:
            raise RuntimeError("Host creation failed")
        return [f"host-{i}" for i in range(len(hosts))]
    
    def create_guests(self, guests, host_mapping):
        if self.fail_guests:
            raise RuntimeError("Guest creation failed")
        return [f"guest-{i}" for i in range(len(guests))]
    
    def destroy_hosts(self, host_ids):
        pass
    
    def destroy_guests(self, guest_ids):
        pass
    
    def get_status(self, resource_ids):
        return {rid: "active" for rid in resource_ids}


class TestRangeOrchestratorExceptions:
    """Test exception handling in RangeOrchestrator"""
    
    @pytest.fixture
    def settings(self, tmp_path):
        """Create test settings"""
        return CyRISSettings(
            cyris_path=tmp_path,
            cyber_range_dir=tmp_path / "cyber_range"
        )
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock provider"""
        return MockProvider()
    
    @pytest.fixture
    def orchestrator(self, settings, mock_provider):
        """Create orchestrator with mocked dependencies"""
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            return RangeOrchestrator(settings, mock_provider)
    
    def test_orchestrator_initialization_success(self, settings, mock_provider):
        """Test successful orchestrator initialization"""
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            orchestrator = RangeOrchestrator(settings, mock_provider)
            
            assert orchestrator.settings == settings
            assert orchestrator.provider == mock_provider
            assert orchestrator.exception_handler is not None
    
    def test_orchestrator_initialization_failure(self, settings, mock_provider):
        """Test orchestrator initialization failure handling"""
        with patch('cyris.services.orchestrator.NetworkTopologyManager', side_effect=RuntimeError("Topology init failed")), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            
            with pytest.raises(RuntimeError, match="Topology init failed"):
                RangeOrchestrator(settings, mock_provider)
    
    def test_create_range_duplicate_id(self, orchestrator):
        """Test creating range with duplicate ID"""
        range_id = "test-range"
        hosts = [MockHost()]
        guests = [MockGuest()]
        
        # Create first range
        orchestrator.create_range(range_id, "Test Range", "Description", hosts, guests)
        
        # Try to create duplicate
        with pytest.raises(CyRISVirtualizationError) as exc_info:
            orchestrator.create_range(range_id, "Duplicate Range", "Description", hosts, guests)
        
        assert "already exists" in str(exc_info.value)
        assert exc_info.value.error_code == CyRISErrorCode.VIRTUALIZATION_ERROR
    
    def test_create_range_host_creation_failure(self, settings, tmp_path):
        """Test range creation with host creation failure"""
        mock_provider = MockProvider(fail_hosts=True)
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            orchestrator = RangeOrchestrator(settings, mock_provider)
        
        hosts = [MockHost()]
        guests = [MockGuest()]
        
        with pytest.raises(CyRISVirtualizationError) as exc_info:
            orchestrator.create_range("test-range", "Test Range", "Description", hosts, guests)
        
        assert "Failed to create hosts" in str(exc_info.value)
        assert exc_info.value.error_context.range_id == "test-range"
    
    def test_create_range_guest_creation_failure(self, settings, tmp_path):
        """Test range creation with guest creation failure"""
        mock_provider = MockProvider(fail_guests=True)
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            orchestrator = RangeOrchestrator(settings, mock_provider)
        
        hosts = [MockHost()]
        guests = [MockGuest()]
        
        with pytest.raises(CyRISVirtualizationError) as exc_info:
            orchestrator.create_range("test-range", "Test Range", "Description", hosts, guests)
        
        assert "Failed to create guests" in str(exc_info.value)
        assert exc_info.value.error_context.range_id == "test-range"
    
    def test_create_range_task_execution_failure(self, orchestrator):
        """Test range creation with task execution failure"""
        hosts = [MockHost()]
        guests = [MockGuest(tasks=[{"add_account": {"account": "testuser", "passwd": "password"}}])]
        
        # Mock task executor to fail
        orchestrator.task_executor.execute_guest_tasks = Mock(side_effect=RuntimeError("Task failed"))
        
        # Range creation should still succeed even if tasks fail (using safe_execute)
        result = orchestrator.create_range("test-range", "Test Range", "Description", hosts, guests)
        
        assert result.range_id == "test-range"
        assert result.status == RangeStatus.ACTIVE
    
    def test_create_range_topology_failure(self, orchestrator):
        """Test range creation with network topology failure"""
        hosts = [MockHost()]
        guests = [MockGuest()]
        topology_config = {"networks": ["test-network"]}
        
        # Mock topology manager to fail - note the create_topology method takes different parameters
        orchestrator.topology_manager.create_topology = Mock(side_effect=RuntimeError("Topology failed"))
        orchestrator.topology_manager.get_guest_ip = Mock(return_value=None)
        
        # Range creation should still succeed (using safe_execute)
        result = orchestrator.create_range("test-range", "Test Range", "Description", hosts, guests, topology_config)
        
        assert result.range_id == "test-range"
        assert result.status == RangeStatus.ACTIVE
    
    def test_create_range_success_with_tasks(self, orchestrator):
        """Test successful range creation with tasks"""
        hosts = [MockHost()]
        guests = [MockGuest(
            ip_addr="192.168.1.100",
            tasks=[{"add_account": {"account": "testuser", "passwd": "password"}}]
        )]
        
        # Mock successful task execution
        mock_task_result = Mock()
        mock_task_result.task_id = "test-task"
        mock_task_result.task_type.value = "add_account"
        mock_task_result.success = True
        mock_task_result.message = "Task completed"
        
        orchestrator.task_executor.execute_guest_tasks = Mock(return_value=[mock_task_result])
        
        result = orchestrator.create_range("test-range", "Test Range", "Description", hosts, guests)
        
        assert result.range_id == "test-range"
        assert result.status == RangeStatus.ACTIVE
        assert 'task_results' in result.tags
    
    def test_create_range_cleanup_on_failure(self, settings, tmp_path):
        """Test cleanup is called when range creation fails"""
        mock_provider = MockProvider(fail_guests=True)
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            orchestrator = RangeOrchestrator(settings, mock_provider)
        
        # Mock cleanup method
        with patch.object(orchestrator, '_cleanup_range_resources') as mock_cleanup:
            hosts = [MockHost()]
            guests = [MockGuest()]
            
            with pytest.raises(CyRISVirtualizationError):
                orchestrator.create_range("test-range", "Test Range", "Description", hosts, guests)
            
            # Cleanup should have been called through safe_execute
            mock_cleanup.assert_called_once_with("test-range")
    
    def test_exception_statistics_tracking(self, orchestrator):
        """Test that exception handler tracks error statistics"""
        hosts = [MockHost()]
        guests = [MockGuest()]
        
        # Create first range successfully
        orchestrator.create_range("range1", "Range 1", "Description", hosts, guests)
        
        # Try to create duplicate - this should trigger an error
        try:
            orchestrator.create_range("range1", "Duplicate", "Description", hosts, guests)  # Duplicate error
        except CyRISVirtualizationError:
            pass
        
        stats = orchestrator.exception_handler.get_error_statistics()
        assert 'VIRTUALIZATION_ERROR' in stats
        assert stats['VIRTUALIZATION_ERROR'] >= 1
    
    def test_safe_execute_with_successful_operation(self, orchestrator):
        """Test safe_execute with successful operation"""
        from cyris.core.exceptions import safe_execute
        
        def successful_operation(x, y):
            return x + y
        
        result = safe_execute(
            successful_operation, 
            5, 10,
            context={"test": "context"},
            logger=orchestrator.logger
        )
        
        assert result == 15
    
    def test_safe_execute_with_failing_operation(self, orchestrator):
        """Test safe_execute with failing operation"""
        from cyris.core.exceptions import safe_execute
        
        def failing_operation():
            raise RuntimeError("Operation failed")
        
        result = safe_execute(
            failing_operation,
            context={"test": "context"},
            default_return="default_value",
            logger=orchestrator.logger
        )
        
        assert result == "default_value"


class TestRangeOrchestratorOtherMethods:
    """Test other orchestrator methods with exception handling"""
    
    @pytest.fixture
    def orchestrator_with_ranges(self, tmp_path):
        """Create orchestrator with some test ranges"""
        settings = CyRISSettings(
            cyris_path=tmp_path,
            cyber_range_dir=tmp_path / "cyber_range"
        )
        mock_provider = MockProvider()
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'):
            orchestrator = RangeOrchestrator(settings, mock_provider)
        
        # Create test ranges
        hosts = [MockHost()]
        guests = [MockGuest()]
        
        orchestrator.create_range("range1", "Range 1", "First range", hosts, guests)
        orchestrator.create_range("range2", "Range 2", "Second range", hosts, guests)
        
        return orchestrator
    
    def test_get_range_existing(self, orchestrator_with_ranges):
        """Test getting existing range"""
        result = orchestrator_with_ranges.get_range("range1")
        
        assert result is not None
        assert result.range_id == "range1"
        assert result.name == "Range 1"
    
    def test_get_range_nonexistent(self, orchestrator_with_ranges):
        """Test getting non-existent range"""
        result = orchestrator_with_ranges.get_range("nonexistent")
        
        assert result is None
    
    def test_list_ranges_all(self, orchestrator_with_ranges):
        """Test listing all ranges"""
        result = orchestrator_with_ranges.list_ranges()
        
        assert len(result) == 2
        assert {r.range_id for r in result} == {"range1", "range2"}
    
    def test_list_ranges_by_status(self, orchestrator_with_ranges):
        """Test listing ranges by status"""
        result = orchestrator_with_ranges.list_ranges(status=RangeStatus.ACTIVE)
        
        assert len(result) == 2
        assert all(r.status == RangeStatus.ACTIVE for r in result)
    
    def test_exception_handler_integration(self, orchestrator_with_ranges):
        """Test exception handler is properly integrated"""
        handler = orchestrator_with_ranges.exception_handler
        
        # Test that handler is working
        test_exception = RuntimeError("Test error")
        context = handler.handle_exception(test_exception)
        
        assert context is not None
        assert "Test error" in context.message
        
        # Check statistics
        stats = handler.get_error_statistics()
        assert 'UNKNOWN_ERROR' in stats