"""
Test Orchestrator Integration with Comprehensive Logging

Tests that the orchestrator properly integrates with the comprehensive logging system
including operation tracking, progress reporting, and status file generation.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.services.orchestrator import RangeOrchestrator, RangeStatus
from cyris.core.log_aggregator import get_range_log_aggregator, LogLevel
from cyris.core.operation_tracker import GLOBAL_OPERATION_TRACKER
from cyris.core.progress import GLOBAL_PROGRESS


class TestOrchestratorLoggingIntegration:
    """Test orchestrator integration with comprehensive logging"""
    
    def setup_method(self):
        """Setup for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create mock settings with proper path attributes
        self.mock_settings = Mock()
        self.mock_settings.cyris_path = self.temp_dir
        self.mock_settings.ranges_dir = self.temp_dir / "ranges"
        self.mock_settings.cyber_range_dir = str(self.temp_dir / "cyber_range")  # String path for pathlib
        self.mock_settings.default_provider = "kvm"
        
        # Create mock provider
        self.mock_provider = Mock()
        self.mock_provider.create_hosts.return_value = ["host1", "host2"]
        self.mock_provider.create_guests.return_value = ["guest1", "guest2"]
        self.mock_provider.get_status.return_value = {"host1": "active", "guest1": "active"}
        
        # Create directories
        self.mock_settings.ranges_dir.mkdir(parents=True, exist_ok=True)
        Path(self.mock_settings.cyber_range_dir).mkdir(parents=True, exist_ok=True)
        
        # Clear global state
        GLOBAL_OPERATION_TRACKER.clear()
        GLOBAL_PROGRESS.clear()
        
    def teardown_method(self):
        """Cleanup after each test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        
        # Clear global state
        GLOBAL_OPERATION_TRACKER.clear()
        GLOBAL_PROGRESS.clear()
    
    @patch('cyris.services.orchestrator.safe_execute')
    @patch('cyris.services.orchestrator.TaskExecutor')
    def test_orchestrator_creates_comprehensive_logs(self, mock_task_executor, mock_safe_execute):
        """Test that orchestrator creates comprehensive logs during range creation"""
        
        # Setup mocks
        mock_safe_execute.side_effect = lambda func, *args, **kwargs: func(*args) if func else []
        mock_task_executor_instance = Mock()
        mock_task_executor_instance.execute_guest_tasks.return_value = []
        mock_task_executor.return_value = mock_task_executor_instance
        
        # Create orchestrator
        orchestrator = RangeOrchestrator(
            settings=self.mock_settings,
            infrastructure_provider=self.mock_provider
        )
        
        # Create simple range
        range_id = "test-range-001"
        hosts = []  # Empty hosts for simple test
        guests = []  # Empty guests for simple test
        
        # Create range (this should set up comprehensive logging)
        with patch('cyris.services.orchestrator.NetworkTopologyManager'):
            with patch('cyris.services.orchestrator.TunnelManager'):
                metadata = orchestrator.create_range(
                    range_id=range_id,
                    name="Test Range",
                    description="Test range for logging integration",
                    hosts=hosts,
                    guests=guests
                )
        
        # Verify range was created
        assert metadata.range_id == range_id
        assert metadata.name == "Test Range"
        
        # Verify comprehensive log files were created
        log_aggregator = get_range_log_aggregator(range_id, self.mock_settings.ranges_dir)
        
        assert log_aggregator.creation_log_file.exists(), "creation.log should be created"
        assert log_aggregator.detailed_log_file.exists(), "detailed.log should be created"
        assert log_aggregator.status_file.exists(), "status file should be created"
        
        # Verify creation.log contains expected content
        creation_content = log_aggregator.creation_log_file.read_text()
        assert "CyRIS Range Creation Log" in creation_content
        assert range_id in creation_content
        assert "Starting range creation" in creation_content
        
        # Verify status file contains success
        status_content = log_aggregator.status_file.read_text().strip()
        assert status_content == "SUCCESS"
    
    def test_orchestrator_logs_contain_legacy_format(self):
        """Test that orchestrator logs contain legacy-style format"""
        range_id = "test-legacy-format"
        log_aggregator = get_range_log_aggregator(range_id, self.temp_dir)
        
        # Test direct logging to range
        from cyris.core.log_aggregator import log_to_range
        
        # Log some test messages
        log_to_range(range_id, LogLevel.INFO, "Start the base VMs.", "orchestrator")
        log_to_range(range_id, LogLevel.INFO, "Check that the base VMs are up.", "orchestrator")
        log_to_range(range_id, LogLevel.INFO, "Clone VMs and create the cyber range.", "orchestrator")
        
        # Verify log file contains legacy-style messages
        creation_content = log_aggregator.creation_log_file.read_text()
        
        # Check for INFO messages in legacy format
        assert "* INFO: cyris:" in creation_content
        assert "Start the base VMs." in creation_content
        assert "Check that the base VMs are up." in creation_content
        assert "Clone VMs and create the cyber range." in creation_content
    
    def test_comprehensive_logging_with_command_execution(self):
        """Test comprehensive logging with command execution tracking"""
        range_id = "test-command-logging"
        log_aggregator = get_range_log_aggregator(range_id, self.temp_dir)
        
        from cyris.core.log_aggregator import log_to_range
        from cyris.core.operation_tracker import set_comprehensive_log_file, execute_command
        
        # Set up logging
        set_comprehensive_log_file(log_aggregator.creation_log_file)
        
        # Log command execution like orchestrator would
        log_aggregator.log_command_execution(
            "virsh list --all",
            "Check VM status command"
        )
        
        # Execute a test command
        execute_command("echo 'test command'", "Test command execution")
        
        # Verify command logging
        creation_content = log_aggregator.creation_log_file.read_text()
        
        assert "-- Check VM status command:" in creation_content
        assert "virsh list --all" in creation_content
        assert "-- Test command execution:" in creation_content
        assert "echo 'test command'" in creation_content
    
    @patch('cyris.services.orchestrator.safe_execute')
    def test_orchestrator_error_handling_with_logging(self, mock_safe_execute):
        """Test that orchestrator properly logs errors and failures"""
        
        # Setup mock to raise exception
        def failing_create_hosts(*args, **kwargs):
            raise Exception("VM creation failed")
        
        mock_safe_execute.side_effect = failing_create_hosts
        
        # Create orchestrator
        orchestrator = RangeOrchestrator(
            settings=self.mock_settings,
            infrastructure_provider=self.mock_provider
        )
        
        range_id = "test-error-range"
        hosts = [Mock()]  # Add a mock host to trigger creation
        
        # Attempt to create range (should fail)
        with pytest.raises(Exception):
            with patch('cyris.services.orchestrator.NetworkTopologyManager'):
                with patch('cyris.services.orchestrator.TunnelManager'):
                    orchestrator.create_range(
                        range_id=range_id,
                        name="Failing Test Range",
                        description="Test range that should fail",
                        hosts=hosts,
                        guests=[]
                    )
        
        # Verify error was logged
        log_aggregator = get_range_log_aggregator(range_id, self.mock_settings.ranges_dir)
        
        # Check that log files exist even on failure
        assert log_aggregator.creation_log_file.exists(), "Log file should exist even on failure"
        
        # Check status file shows failure
        if log_aggregator.status_file.exists():
            status_content = log_aggregator.status_file.read_text().strip()
            assert status_content == "FAILURE", f"Expected FAILURE but got {status_content}"
    
    def test_log_aggregator_operation_context_tracking(self):
        """Test log aggregator operation context tracking"""
        range_id = "test-context-tracking"
        log_aggregator = get_range_log_aggregator(range_id, self.temp_dir)
        
        # Test operation context like orchestrator uses
        log_aggregator.start_operation_context("range_creation", "RANGE_CREATE", "Create test range")
        
        # Add some logs
        log_aggregator.log(LogLevel.INFO, "Creating VMs", operation_id="range_creation")
        log_aggregator.log(LogLevel.INFO, "Configuring network", operation_id="range_creation")
        
        # End operation context
        log_aggregator.end_operation_context("range_creation", True, "Range created successfully")
        
        # Write final status
        log_aggregator.write_final_status(True, 0)
        
        # Verify operation was tracked
        summary = log_aggregator.get_operation_summary()
        assert summary['total_operations'] == 1
        assert summary['successful_operations'] == 1
        assert summary['failed_operations'] == 0
        
        # Verify final status
        status_content = log_aggregator.status_file.read_text().strip()
        assert status_content == "SUCCESS"
        
        # Verify creation log contains operation summary
        creation_content = log_aggregator.creation_log_file.read_text()
        assert "Creation result: SUCCESS" in creation_content
        assert "Operation Summary: 1 successful, 0 failed" in creation_content


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])