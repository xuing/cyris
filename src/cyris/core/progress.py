"""
Enhanced Progress Tracking System

Provides comprehensive legacy-style progress reporting with clear INFO messages, 
operation tracking, and integration with the comprehensive logging system.
Designed to restore the straightforward feedback from the legacy CyRIS system
while maintaining modern architecture capabilities.
"""

import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum


class OperationStatus(Enum):
    """Simple operation status tracking"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OperationStep:
    """Individual operation step tracking"""
    step_id: str
    description: str
    status: OperationStatus = OperationStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def start(self) -> None:
        """Mark step as started"""
        self.status = OperationStatus.IN_PROGRESS
        self.start_time = time.time()
    
    def complete(self) -> None:
        """Mark step as completed"""
        self.status = OperationStatus.COMPLETED
        self.end_time = time.time()
    
    def fail(self, error: str) -> None:
        """Mark step as failed"""
        self.status = OperationStatus.FAILED
        self.end_time = time.time()
        self.error_message = error
    
    @property
    def duration(self) -> Optional[float]:
        """Get operation duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class ProgressTracker:
    """
    Enhanced progress tracker providing legacy-style INFO messages
    
    Restores the clear, informative progress reporting from the original CyRIS system
    with integration to comprehensive logging and status file generation.
    """
    
    def __init__(self, operation_name: str, log_file: Optional[Union[str, Path]] = None):
        self.operation_name = operation_name
        self.steps: List[OperationStep] = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.overall_success = True
        self.log_file = Path(log_file) if log_file else None
        # Track all progress messages for comprehensive logging
        self.progress_log: List[str] = []
        
    def add_step(self, step_id: str, description: str) -> OperationStep:
        """Add a new step to track"""
        step = OperationStep(step_id, description)
        self.steps.append(step)
        return step
    
    def start_step(self, step_id: str) -> None:
        """Start a specific step and print INFO message"""
        step = self._find_step(step_id)
        if step:
            step.start()
            self._print_info(step.description)
    
    def complete_step(self, step_id: str) -> None:
        """Complete a specific step"""
        step = self._find_step(step_id)
        if step:
            step.complete()
    
    def fail_step(self, step_id: str, error: str) -> None:
        """Fail a specific step and mark overall operation as failed"""
        step = self._find_step(step_id)
        if step:
            step.fail(error)
            self.overall_success = False
            self._print_error(f"{error}")
        else:
            # If step doesn't exist, just print the error
            self.overall_success = False
            self._print_error(f"{error}")
    
    def info(self, message: str) -> None:
        """Print an INFO message in legacy style"""
        self._print_info(message)
    
    def complete(self) -> None:
        """Complete the overall operation and show summary"""
        self.end_time = time.time()
        
        # Print completion summary
        duration = self.end_time - self.start_time
        
        if self.overall_success:
            self._print_success(f"Creation result: SUCCESS (took {duration:.1f}s)")
        else:
            failed_steps = [step for step in self.steps if step.status == OperationStatus.FAILED]
            self._print_error(f"Creation result: FAILED ({len(failed_steps)} errors)")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get operation summary for logging/debugging"""
        return {
            'operation': self.operation_name,
            'success': self.overall_success,
            'duration': self.duration,
            'steps_completed': len([s for s in self.steps if s.status == OperationStatus.COMPLETED]),
            'steps_failed': len([s for s in self.steps if s.status == OperationStatus.FAILED]),
            'steps_total': len(self.steps)
        }
    
    @property
    def duration(self) -> Optional[float]:
        """Get total operation duration"""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    def print_legacy_messages(self) -> None:
        """Print common legacy-style progress messages for range creation"""
        # These are the common messages from the legacy system
        legacy_messages = [
            "Start the base VMs.",
            "Check that the base VMs are up.",
            "Shut down the base VMs before cloning.",
            "Clone VMs and create the cyber range.",
            "Wait for the cloned VMs to start.",
            "Set up firewall rules for the cloned VMs.",
            "Configure network topology for the range.",
            "Execute tasks on the cloned VMs.",
            "Verify task execution results."
        ]
        
        for i, message in enumerate(legacy_messages):
            step_id = f"legacy_step_{i+1:02d}"
            step = self.add_step(step_id, message)
            self.start_step(step_id)
            # In real usage, complete_step would be called when the operation finishes
    
    def report_vm_operation(self, vm_name: str, operation: str, success: bool = True) -> None:
        """Report VM-specific operation in legacy style"""
        if success:
            self.info(f"{operation} VM '{vm_name}' completed successfully.")
        else:
            self.fail_step("vm_operation", f"{operation} VM '{vm_name}' failed.")
    
    def report_network_operation(self, operation: str, details: str = "") -> None:
        """Report network operation in legacy style"""
        message = f"{operation}"
        if details:
            message += f": {details}"
        self.info(message)
    
    def report_task_execution(self, task_count: int, vm_name: str) -> None:
        """Report task execution in legacy style"""
        self.info(f"Executing {task_count} tasks on VM '{vm_name}'.")
    
    def get_progress_log(self) -> List[str]:
        """Get all progress messages for auditing"""
        return self.progress_log.copy()
    
    def write_progress_to_file(self, file_path: Union[str, Path]) -> None:
        """Write all progress messages to a file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Progress Log for: {self.operation_name}\n")
                f.write(f"Started at: {datetime.fromtimestamp(self.start_time)}\n")
                if self.end_time:
                    f.write(f"Completed at: {datetime.fromtimestamp(self.end_time)}\n")
                    f.write(f"Duration: {self.duration:.2f} seconds\n")
                f.write(f"Overall Success: {self.overall_success}\n")
                f.write("\n--- Progress Messages ---\n")
                for message in self.progress_log:
                    f.write(f"{message}\n")
        except Exception as e:
            self._print_error(f"Failed to write progress log to {file_path}: {e}")
    
    def _find_step(self, step_id: str) -> Optional[OperationStep]:
        """Find step by ID"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def _print_info(self, message: str) -> None:
        """Print INFO message in legacy format with logging integration"""
        formatted_message = f"* INFO: cyris: {message}"
        print(formatted_message)
        self.progress_log.append(formatted_message)
        self._write_to_log_file(formatted_message)
    
    def _print_error(self, message: str) -> None:
        """Print ERROR message in legacy format with logging integration"""
        formatted_message = f"* ERROR: cyris: {message}"
        print(formatted_message)
        self.progress_log.append(formatted_message)
        self._write_to_log_file(formatted_message)
    
    def _print_success(self, message: str) -> None:
        """Print SUCCESS message in legacy format with logging integration"""
        formatted_message = f"* INFO: cyris: {message}"
        print(formatted_message)
        self.progress_log.append(formatted_message)
        self._write_to_log_file(formatted_message)
    
    def _write_to_log_file(self, message: str) -> None:
        """Write message to log file if available"""
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {message}\n")
            except Exception as e:
                # Don't fail progress tracking due to logging issues
                pass


class GlobalProgressTracker:
    """
    Global progress tracker for system-wide operation coordination
    
    Similar to legacy RESPONSE_LIST for tracking all operations atomically.
    """
    
    def __init__(self):
        self.operations: Dict[str, ProgressTracker] = {}
        self.global_responses: List[Any] = []  # Similar to legacy RESPONSE_LIST
        
    def create_operation(self, operation_id: str, operation_name: str) -> ProgressTracker:
        """Create a new operation tracker"""
        tracker = ProgressTracker(operation_name)
        self.operations[operation_id] = tracker
        return tracker
    
    def get_operation(self, operation_id: str) -> Optional[ProgressTracker]:
        """Get existing operation tracker"""
        return self.operations.get(operation_id)
    
    def record_response(self, response: Any) -> None:
        """Record operation response (similar to legacy RESPONSE_LIST.append())"""
        self.global_responses.append(response)
    
    def is_all_successful(self) -> bool:
        """Check if all tracked operations are successful"""
        return all(tracker.overall_success for tracker in self.operations.values())
    
    def get_failed_operations(self) -> List[str]:
        """Get list of failed operation IDs"""
        return [op_id for op_id, tracker in self.operations.items() 
                if not tracker.overall_success]
    
    def clear(self) -> None:
        """Clear all tracked operations (for cleanup)"""
        self.operations.clear()
        self.global_responses.clear()


# Global instance for system-wide coordination (similar to legacy RESPONSE_LIST)
GLOBAL_PROGRESS = GlobalProgressTracker()


def create_progress_tracker(operation_id: str, operation_name: str) -> ProgressTracker:
    """Convenience function to create a progress tracker"""
    return GLOBAL_PROGRESS.create_operation(operation_id, operation_name)


def get_progress_tracker(operation_id: str) -> Optional[ProgressTracker]:
    """Convenience function to get a progress tracker"""
    return GLOBAL_PROGRESS.get_operation(operation_id)


def record_operation_response(response: Any) -> None:
    """Convenience function to record operation response globally"""
    GLOBAL_PROGRESS.record_response(response)