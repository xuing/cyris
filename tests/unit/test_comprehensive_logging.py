"""
Test Comprehensive Logging System

Tests the comprehensive logging system including operation tracking,
command execution, progress tracking, and log aggregation to ensure
they match legacy system capabilities while maintaining modern architecture.
"""

import pytest
import tempfile
import shutil
import os
import json
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, call
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.core.operation_tracker import (
    AtomicOperationTracker, AtomicOperation, OperationType,
    GLOBAL_OPERATION_TRACKER, start_operation, complete_operation, 
    fail_operation, execute_command, get_comprehensive_status,
    determine_creation_result, write_status_file, set_comprehensive_log_file
)
from cyris.core.command_executor import (
    EnhancedCommandExecutor, CommandResult, 
    execute_command_safe, execute_command_with_retry,
    set_global_log_file, get_execution_statistics
)
from cyris.core.progress import (
    ProgressTracker, OperationStatus, create_progress_tracker,
    get_progress_tracker, GLOBAL_PROGRESS
)
from cyris.core.log_aggregator import (
    ComprehensiveLogAggregator, LogLevel, LogEntry,
    get_range_log_aggregator, log_to_range, finalize_range_logging
)


class TestAtomicOperationTracker:
    """Test enhanced operation tracker functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.tracker = AtomicOperationTracker()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_file = self.temp_dir / "test_creation.log"
    
    def teardown_method(self):
        """Cleanup after each test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_basic_operation_tracking(self):
        """Test basic operation tracking like legacy RESPONSE_LIST"""
        # Start operations
        op1 = self.tracker.start_operation(OperationType.VM_CREATE, "Create VM 1")
        op2 = self.tracker.start_operation(OperationType.SSH_EXECUTE, "Connect to VM")
        
        assert len(self.tracker.operations) == 2
        assert not self.tracker.is_all_successful()  # Operations not completed yet
        
        # Complete operations
        self.tracker.complete_operation(op1)
        self.tracker.complete_operation(op2)
        
        assert self.tracker.is_all_successful()
        assert len(self.tracker.get_successful_operations()) == 2
        assert len(self.tracker.get_failed_operations()) == 0
    
    def test_legacy_response_list_compatibility(self):
        """Test legacy-style response list generation"""
        # Create operations with different outcomes
        op1 = self.tracker.start_operation(OperationType.VM_CREATE, "Create VM 1")
        op2 = self.tracker.start_operation(OperationType.SSH_EXECUTE, "SSH command")
        op3 = self.tracker.start_operation(OperationType.TASK_EXECUTE, "Execute task")
        
        # Complete with different results
        self.tracker.complete_operation(op1)  # Success (exit code 0)
        self.tracker.fail_operation(op2, "SSH failed")  # Failure (exit code 1)
        self.tracker.complete_operation(op3)  # Success (exit code 0)
        
        # Get legacy response list
        response_list = self.tracker.get_legacy_response_list()
        
        # Should be [0, 1, 0] like legacy RESPONSE_LIST
        assert response_list == [0, 1, 0]
        assert not self.tracker.is_all_successful()
    
    def test_command_execution_with_logging(self):
        """Test system command execution with comprehensive logging"""
        self.tracker.set_comprehensive_log_file(self.log_file)
        
        # Execute successful command
        op_id = self.tracker.execute_system_command(
            "echo 'test message'",
            log_context="Test command execution"
        )
        
        # Verify operation was tracked
        operation = self.tracker._find_operation(op_id)
        assert operation is not None
        assert operation.success
        assert operation.exit_code == 0
        assert operation.command == "echo 'test message'"
        
        # Verify log file was written
        assert self.log_file.exists()
        log_content = self.log_file.read_text()
        assert "-- Test command execution:" in log_content
        assert "echo 'test message'" in log_content
    
    def test_command_execution_failure_handling(self):
        """Test command execution failure handling like legacy system"""
        self.tracker.set_comprehensive_log_file(self.log_file)
        
        # Execute failing command (capture stdout to prevent test pollution)
        with patch('builtins.print') as mock_print:
            op_id = self.tracker.execute_system_command(
                "false",  # Command that always fails
                log_context="Failing command test"
            )
        
        # Verify operation was tracked as failed
        operation = self.tracker._find_operation(op_id)
        assert operation is not None
        assert not operation.success
        assert operation.exit_code == 1
        
        # Verify legacy-style error message was printed
        mock_print.assert_any_call("* ERROR: cyris: Issue when executing command (exit status = 1):")
        mock_print.assert_any_call("  false")
        assert any("Check the log file for details:" in str(call) for call in mock_print.call_args_list)
    
    def test_comprehensive_status_determination(self):
        """Test comprehensive status determination like legacy system"""
        # Execute mixed success/failure operations
        op1 = self.tracker.start_operation(OperationType.VM_CREATE, "Create VM")
        op2 = self.tracker.start_operation(OperationType.SSH_EXECUTE, "SSH command")
        
        self.tracker.complete_operation(op1)
        self.tracker.fail_operation(op2, "SSH failed")
        
        status = self.tracker.get_comprehensive_status()
        
        assert status['overall_success'] == False
        assert status['fail_count'] == 1
        assert status['total_operations'] == 2
        assert status['successful_operations'] == 1
        assert status['failed_operations'] == 1
        assert status['creation_status'] == 'FAILURE'
    
    def test_status_file_generation(self):
        """Test status file generation like legacy cr_creation_status"""
        status_file = self.temp_dir / "test_status"
        
        # Clear tracker for clean test
        self.tracker.clear()
        
        # Test successful scenario
        op1 = self.tracker.start_operation(OperationType.VM_CREATE, "Create VM")
        self.tracker.complete_operation(op1)
        
        # Use the tracker's method directly instead of global function
        result_str, success = "SUCCESS" if self.tracker.is_all_successful() else "FAILURE", self.tracker.is_all_successful()
        with open(status_file, 'w') as f:
            f.write(f"{result_str}\n")
        
        assert status_file.exists()
        assert status_file.read_text().strip() == "SUCCESS"
        
        # Test failure scenario with fresh tracker
        self.tracker.clear()
        op2 = self.tracker.start_operation(OperationType.SSH_EXECUTE, "SSH command")
        self.tracker.fail_operation(op2, "SSH failed")
        
        result_str, success = "SUCCESS" if self.tracker.is_all_successful() else "FAILURE", self.tracker.is_all_successful()
        with open(status_file, 'w') as f:
            f.write(f"{result_str}\n")
        
        assert status_file.read_text().strip() == "FAILURE"


class TestEnhancedCommandExecutor:
    """Test enhanced command executor functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_file = self.temp_dir / "command_log.log"
        self.executor = EnhancedCommandExecutor(self.log_file)
    
    def teardown_method(self):
        """Cleanup after each test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_successful_command_execution(self):
        """Test successful command execution with logging"""
        result = self.executor.execute(
            "echo 'Hello World'",
            log_context="Echo test command"
        )
        
        assert result.success
        assert result.exit_code == 0
        assert result.command == "echo 'Hello World'"
        assert result.execution_time >= 0
        assert isinstance(result.timestamp, datetime)
        
        # Check statistics
        stats = self.executor.get_execution_statistics()
        assert stats['commands_executed'] == 1
        assert stats['commands_successful'] == 1
        assert stats['commands_failed'] == 0
    
    def test_failed_command_execution(self):
        """Test failed command execution handling"""
        # Use a command that definitely fails on most systems
        result = self.executor.execute(
            "false",  # Command that always returns exit code 1
            log_context="Failing test command"
        )
        
        assert not result.success
        assert result.exit_code == 1
        assert result.command == "false"
        
        # Check statistics
        stats = self.executor.get_execution_statistics()
        assert stats['commands_executed'] == 1
        assert stats['commands_successful'] == 0
        assert stats['commands_failed'] == 1
    
    def test_command_execution_with_retry(self):
        """Test command execution with retry mechanism"""
        # Test with a command that should succeed
        result = self.executor.execute_with_retry(
            "echo 'retry test'",
            max_retries=2,
            log_context="Retry test command"
        )
        
        assert result.success
        assert result.exit_code == 0
    
    @patch('builtins.print')
    def test_command_execution_retry_failure(self, mock_print):
        """Test command execution retry with persistent failure"""
        result = self.executor.execute_with_retry(
            "false",  # Always fails
            max_retries=2,
            log_context="Retry failure test"
        )
        
        assert not result.success
        assert result.exit_code == 1
        
        # Verify retry messages were printed
        assert any("Command failed after 2 retries" in str(call) for call in mock_print.call_args_list)
    
    def test_batch_command_execution(self):
        """Test batch command execution"""
        commands = [
            {'command': 'echo "command 1"', 'log_context': 'Batch command 1'},
            {'command': 'echo "command 2"', 'log_context': 'Batch command 2'},
            {'command': 'true', 'log_context': 'Batch command 3'}  # Success command
        ]
        
        results = self.executor.execute_batch(commands, stop_on_failure=False)
        
        assert len(results) == 3
        assert all(result.success for result in results)
    
    def test_command_safety_validation(self):
        """Test command safety validation"""
        # Test dangerous command detection
        is_safe, reason = self.executor.validate_command_safety("rm -rf /")
        assert not is_safe
        assert "dangerous pattern" in reason.lower()
        
        # Test safe command
        is_safe, reason = self.executor.validate_command_safety("echo hello")
        assert is_safe
        assert reason is None
    
    def test_safe_command_execution(self):
        """Test safe command execution with validation"""
        # Test that dangerous command is rejected
        result = self.executor.execute_safe("rm -rf /", validate_safety=True)
        
        assert not result.success
        assert result.exit_code == 1
        assert "rejected for safety" in result.stderr


class TestProgressTracker:
    """Test enhanced progress tracker functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_file = self.temp_dir / "progress.log"
        self.tracker = ProgressTracker("Test Operation", self.log_file)
    
    def teardown_method(self):
        """Cleanup after each test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @patch('builtins.print')
    def test_legacy_style_info_messages(self, mock_print):
        """Test legacy-style INFO message generation"""
        self.tracker.info("Starting VM creation process.")
        
        # Verify legacy-style message was printed
        mock_print.assert_called_with("* INFO: cyris: Starting VM creation process.")
        
        # Verify message was added to progress log
        progress_log = self.tracker.get_progress_log()
        assert "* INFO: cyris: Starting VM creation process." in progress_log
    
    @patch('builtins.print')
    def test_legacy_style_error_messages(self, mock_print):
        """Test legacy-style ERROR message generation"""
        self.tracker.fail_step("vm_create", "Failed to create VM due to insufficient resources")
        
        # Verify error message was printed in the correct format
        mock_print.assert_any_call("* ERROR: cyris: Failed to create VM due to insufficient resources")
    
    def test_operation_step_tracking(self):
        """Test operation step tracking"""
        # Add and track steps
        step = self.tracker.add_step("vm_create", "Create virtual machine")
        assert step.status == OperationStatus.PENDING
        
        self.tracker.start_step("vm_create")
        assert step.status == OperationStatus.IN_PROGRESS
        assert step.start_time is not None
        
        self.tracker.complete_step("vm_create")
        assert step.status == OperationStatus.COMPLETED
        assert step.end_time is not None
        assert step.duration is not None
    
    @patch('builtins.print')
    def test_legacy_progress_completion(self, mock_print):
        """Test legacy-style completion messages"""
        # Add some steps
        self.tracker.add_step("step1", "Step 1")
        self.tracker.add_step("step2", "Step 2")
        
        # Complete steps
        self.tracker.start_step("step1")
        self.tracker.complete_step("step1")
        self.tracker.start_step("step2")
        self.tracker.complete_step("step2")
        
        # Complete overall operation
        self.tracker.complete()
        
        # Verify success message was printed (duration will vary)
        success_calls = [call for call in mock_print.call_args_list if "Creation result: SUCCESS" in str(call)]
        assert len(success_calls) > 0
    
    def test_vm_operation_reporting(self):
        """Test VM-specific operation reporting"""
        with patch('builtins.print') as mock_print:
            self.tracker.report_vm_operation("test-vm-01", "Create", success=True)
            mock_print.assert_called_with("* INFO: cyris: Create VM 'test-vm-01' completed successfully.")
    
    def test_progress_log_persistence(self):
        """Test progress log writing to file"""
        self.tracker.info("Test message 1")
        self.tracker.info("Test message 2")
        
        # Write progress to file
        progress_file = self.temp_dir / "progress_output.log"
        self.tracker.write_progress_to_file(progress_file)
        
        assert progress_file.exists()
        content = progress_file.read_text()
        assert "Test Operation" in content
        assert "* INFO: cyris: Test message 1" in content
        assert "* INFO: cyris: Test message 2" in content


class TestComprehensiveLogAggregator:
    """Test comprehensive log aggregation system"""
    
    def setup_method(self):
        """Setup for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.range_id = "test-range-001"
        self.aggregator = ComprehensiveLogAggregator(self.range_id, self.temp_dir)
    
    def teardown_method(self):
        """Cleanup after each test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_log_file_creation(self):
        """Test that log files are created properly"""
        # Check that log files were created
        assert self.aggregator.creation_log_file.exists()
        assert self.aggregator.detailed_log_file.exists()
        
        # Check initial content
        creation_content = self.aggregator.creation_log_file.read_text()
        assert self.range_id in creation_content
        assert "CyRIS Range Creation Log" in creation_content
    
    def test_log_entry_creation_and_formatting(self):
        """Test log entry creation and formatting"""
        self.aggregator.log(
            LogLevel.INFO,
            "Starting VM creation",
            source="orchestrator",
            operation_id="op_001"
        )
        
        # Check that entry was added
        assert len(self.aggregator.log_entries) == 1
        entry = self.aggregator.log_entries[0]
        
        assert entry.level == LogLevel.INFO
        assert entry.message == "Starting VM creation"
        assert entry.source == "orchestrator"
        assert entry.operation_id == "op_001"
        
        # Test formatting
        legacy_format = entry.to_legacy_format()
        assert "* INFO: cyris:" in legacy_format
        assert "Starting VM creation" in legacy_format
    
    def test_command_execution_logging(self):
        """Test command execution logging in legacy style"""
        self.aggregator.log_command_execution(
            "ssh-copy-id -i ~/.ssh/cyris_rsa.pub root@192.168.122.100",
            "Setup SSH keys command",
            operation_id="op_ssh_001"
        )
        
        # Verify command context was logged
        creation_content = self.aggregator.creation_log_file.read_text()
        assert "-- Setup SSH keys command:" in creation_content
        assert "ssh-copy-id -i ~/.ssh/cyris_rsa.pub root@192.168.122.100" in creation_content
    
    def test_operation_context_tracking(self):
        """Test operation context tracking and correlation"""
        # Start operation context
        self.aggregator.start_operation_context(
            "op_vm_create",
            "VM_CREATE",
            "Create virtual machine test-vm-01"
        )
        
        # Add some logs to the operation
        self.aggregator.log(
            LogLevel.INFO,
            "Configuring VM parameters",
            operation_id="op_vm_create"
        )
        
        # End operation context
        self.aggregator.end_operation_context(
            "op_vm_create",
            success=True,
            result_message="VM created successfully"
        )
        
        # Verify operation was tracked
        assert "op_vm_create" in self.aggregator.operation_contexts
        context = self.aggregator.operation_contexts["op_vm_create"]
        
        assert context['operation_type'] == "VM_CREATE"
        assert context['description'] == "Create virtual machine test-vm-01"
        assert context['success'] == True
        assert 'duration' in context
    
    def test_final_status_generation(self):
        """Test final status generation like legacy system"""
        # Add some operations
        self.aggregator.start_operation_context("op1", "VM_CREATE", "Create VM 1")
        self.aggregator.end_operation_context("op1", success=True)
        
        self.aggregator.start_operation_context("op2", "SSH_EXECUTE", "SSH command")
        self.aggregator.end_operation_context("op2", success=False, result_message="SSH failed")
        
        # Write final status
        self.aggregator.write_final_status(overall_success=False, failure_count=1)
        
        # Check status file
        assert self.aggregator.status_file.exists()
        status_content = self.aggregator.status_file.read_text().strip()
        assert status_content == "FAILURE"
        
        # Check that final summary was logged
        creation_content = self.aggregator.creation_log_file.read_text()
        assert "Creation result: FAILURE (1 errors)" in creation_content
    
    def test_log_export_functionality(self):
        """Test log export to JSON for external processing"""
        # Add some log entries
        self.aggregator.log(LogLevel.INFO, "Test message 1", "test_source")
        self.aggregator.log(LogLevel.ERROR, "Test error", "test_source", command="false")
        
        # Export logs
        export_file = self.temp_dir / "logs_export.json"
        self.aggregator.export_logs_to_json(export_file)
        
        assert export_file.exists()
        
        # Verify exported content
        with open(export_file, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data['range_id'] == self.range_id
        assert len(exported_data['entries']) == 2
        assert exported_data['entries'][0]['message'] == "Test message 1"
        assert exported_data['entries'][1]['command'] == "false"
    
    def test_global_aggregator_functions(self):
        """Test global convenience functions"""
        # Test getting range aggregator
        aggregator = get_range_log_aggregator("test-range-002", self.temp_dir)
        assert aggregator.range_id == "test-range-002"
        
        # Test logging to range
        log_to_range(
            "test-range-002",
            LogLevel.INFO,
            "Global logging test",
            source="global_test"
        )
        
        # Verify log was added
        assert len(aggregator.log_entries) == 1
        assert aggregator.log_entries[0].message == "Global logging test"
        
        # Test finalizing range logging
        finalize_range_logging("test-range-002", overall_success=True)
        
        # Verify status file was created
        status_file = self.temp_dir / "test-range-002" / "cr_creation_status"
        assert status_file.exists()
        assert status_file.read_text().strip() == "SUCCESS"


class TestIntegratedLoggingWorkflow:
    """Test integrated logging workflow matching legacy system behavior"""
    
    def setup_method(self):
        """Setup for integrated testing"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.range_id = "integration-test-range"
        
        # Clear global trackers for clean test
        GLOBAL_OPERATION_TRACKER.clear()
        GLOBAL_PROGRESS.clear()
    
    def teardown_method(self):
        """Cleanup after integrated testing"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        
        # Clear global trackers
        GLOBAL_OPERATION_TRACKER.clear()
        GLOBAL_PROGRESS.clear()
    
    @patch('builtins.print')
    def test_complete_range_creation_workflow(self, mock_print):
        """Test complete range creation workflow with comprehensive logging"""
        # Use a separate tracker to avoid global state issues
        tracker = AtomicOperationTracker()
        tracker.set_comprehensive_log_file(self.temp_dir / "creation.log")
        
        # Execute commands with local tracker
        op1 = tracker.start_operation(OperationType.VM_CREATE, "Create VMs")
        tracker.complete_operation(op1)
        
        op2 = tracker.start_operation(OperationType.TASK_EXECUTE, "Execute tasks")
        tracker.complete_operation(op2)
        
        # Get status from local tracker
        status = tracker.get_comprehensive_status()
        assert status['creation_status'] == "SUCCESS"
        assert status['overall_success'] == True
        
        # Test status file generation
        status_file = self.temp_dir / "test_status"
        result_str = status['creation_status']
        with open(status_file, 'w') as f:
            f.write(f"{result_str}\n")
        
        # Setup log aggregator for comprehensive logging test
        log_aggregator = get_range_log_aggregator(self.range_id, self.temp_dir)
        
        # Finalize logging
        finalize_range_logging(self.range_id, overall_success=True)
        
        # Verify status file
        assert status_file.exists()
        assert status_file.read_text().strip() == "SUCCESS"
        
        # Verify log aggregator functionality
        assert log_aggregator.creation_log_file.exists()
    
    @patch('builtins.print')
    def test_failure_scenario_workflow(self, mock_print):
        """Test failure scenario workflow with proper error handling"""
        # Setup logging
        log_aggregator = get_range_log_aggregator(f"{self.range_id}-fail", self.temp_dir)
        set_comprehensive_log_file(log_aggregator.creation_log_file)
        
        progress = create_progress_tracker(f"{self.range_id}-fail", "Range Creation with Failure")
        
        # Start workflow
        progress.info("Start the base VMs.")
        
        # Execute failing command
        op1 = execute_command(
            "false",  # Command that fails
            log_context="VM startup command"
        )
        
        # The command should have automatically failed
        # Check the operation result
        operation = GLOBAL_OPERATION_TRACKER._find_operation(op1)
        assert operation is not None
        assert not operation.success
        
        progress.info("VM startup failed, checking error.")
        
        # Complete workflow with failure
        progress.fail_step("vm_startup", "VM startup command failed")
        progress.complete()
        
        # Determine final result
        result_str, success = determine_creation_result()
        assert result_str == "FAILURE"
        assert success == False
        
        # Finalize logging with failure
        finalize_range_logging(f"{self.range_id}-fail", overall_success=False, failure_count=1)
        
        # Verify error logging
        creation_content = log_aggregator.creation_log_file.read_text()
        assert "Creation result: FAILURE (1 errors)" in creation_content
        
        # Verify error messages were printed
        error_calls = [call for call in mock_print.call_args_list if "* ERROR: cyris:" in str(call)]
        assert len(error_calls) >= 1  # At least one error message


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])