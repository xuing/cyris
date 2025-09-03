"""
Comprehensive Operation Tracker

Provides centralized operation tracking similar to legacy RESPONSE_LIST with enhanced
command execution logging, audit trail generation, and comprehensive success/failure 
determination. Matches legacy logging capabilities while maintaining modern architecture.
"""

import threading
import subprocess
import os
from pathlib import Path
from typing import Any, List, Dict, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging


class OperationType(Enum):
    """Types of operations that can be tracked"""
    VM_CREATE = "vm_create"
    VM_DESTROY = "vm_destroy" 
    VM_START = "vm_start"
    VM_STOP = "vm_stop"
    SSH_EXECUTE = "ssh_execute"
    NETWORK_SETUP = "network_setup"
    TASK_EXECUTE = "task_execute"
    FILE_COPY = "file_copy"
    USER_CREATE = "user_create"
    PARALLEL_OPERATION = "parallel_operation"
    COMMAND_EXECUTE = "command_execute"  # Added for command execution tracking
    SYSTEM_OPERATION = "system_operation"  # Added for general system operations


@dataclass
class AtomicOperation:
    """Individual atomic operation with comprehensive logging support"""
    operation_id: str
    operation_type: OperationType
    description: str
    success: bool = False
    error_message: Optional[str] = None
    result_data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    rollback_function: Optional[Callable] = None
    # Enhanced fields for comprehensive logging
    command: Optional[str] = None  # Command executed for this operation
    exit_code: Optional[int] = None  # Exit code for command operations
    output: Optional[str] = None  # Command output
    log_context: Optional[str] = None  # Context header for logging
    audit_trail: List[str] = field(default_factory=list)  # Detailed audit trail
    
    def mark_success(self, result_data: Any = None, exit_code: Optional[int] = None, output: Optional[str] = None) -> None:
        """Mark operation as successful with optional command details"""
        self.success = True
        self.result_data = result_data
        self.exit_code = exit_code or 0
        self.output = output
        self.timestamp = datetime.now()
        if exit_code is not None:
            self.audit_trail.append(f"Operation completed successfully (exit code: {exit_code})")
        
    def mark_failure(self, error_message: str, exit_code: Optional[int] = None, output: Optional[str] = None) -> None:
        """Mark operation as failed with optional command details"""
        self.success = False
        self.error_message = error_message
        self.exit_code = exit_code
        self.output = output
        self.timestamp = datetime.now()
        self.audit_trail.append(f"Operation failed: {error_message}")
        if exit_code is not None:
            self.audit_trail.append(f"Exit code: {exit_code}")
    
    def add_audit_entry(self, entry: str) -> None:
        """Add entry to audit trail"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.audit_trail.append(f"[{timestamp}] {entry}")
    
    def set_command_info(self, command: str, log_context: Optional[str] = None) -> None:
        """Set command information for this operation"""
        self.command = command
        self.log_context = log_context
        self.add_audit_entry(f"Command set: {command}")
    
    def get_legacy_exit_code(self) -> int:
        """Get legacy-style exit code (0 for success, non-zero for failure)"""
        if self.success:
            return self.exit_code or 0
        else:
            return self.exit_code or 1
        
    def can_rollback(self) -> bool:
        """Check if operation can be rolled back"""
        return self.rollback_function is not None
        
    def rollback(self) -> bool:
        """Attempt to rollback operation"""
        if not self.can_rollback():
            return False
        
        try:
            self.rollback_function()
            return True
        except Exception as e:
            logging.error(f"Rollback failed for {self.operation_id}: {e}")
            return False


class AtomicOperationTracker:
    """
    Comprehensive atomic operation tracker
    
    Similar to legacy RESPONSE_LIST, but with enhanced command execution logging,
    audit trail generation, and comprehensive success/failure determination.
    Provides centralized tracking for all system operations with detailed logging.
    """
    
    def __init__(self):
        self.operations: List[AtomicOperation] = []
        self._lock = threading.RLock()
        self._operation_counter = 0
        # Legacy-compatible response list for exit codes
        self._response_list: List[int] = []  # Like legacy RESPONSE_LIST
        self.comprehensive_log_file: Optional[Path] = None
        
    def start_operation(
        self, 
        operation_type: OperationType, 
        description: str,
        rollback_function: Optional[Callable] = None
    ) -> str:
        """Start tracking a new atomic operation"""
        with self._lock:
            self._operation_counter += 1
            operation_id = f"{operation_type.value}_{self._operation_counter}"
            
            operation = AtomicOperation(
                operation_id=operation_id,
                operation_type=operation_type,
                description=description,
                rollback_function=rollback_function
            )
            
            self.operations.append(operation)
            return operation_id
    
    def complete_operation(self, operation_id: str, result_data: Any = None) -> bool:
        """Mark operation as completed successfully"""
        with self._lock:
            operation = self._find_operation(operation_id)
            if operation:
                operation.mark_success(result_data)
                return True
            return False
    
    def fail_operation(self, operation_id: str, error_message: str) -> bool:
        """Mark operation as failed"""
        with self._lock:
            operation = self._find_operation(operation_id)
            if operation:
                operation.mark_failure(error_message)
                return True
            return False
    
    def is_all_successful(self) -> bool:
        """Check if all operations are successful (similar to legacy success check)"""
        with self._lock:
            return all(op.success for op in self.operations)
    
    def get_failed_operations(self) -> List[AtomicOperation]:
        """Get all failed operations"""
        with self._lock:
            return [op for op in self.operations if not op.success]
    
    def get_successful_operations(self) -> List[AtomicOperation]:
        """Get all successful operations"""
        with self._lock:
            return [op for op in self.operations if op.success]
    
    def get_operation_count(self) -> Dict[str, int]:
        """Get operation count summary"""
        with self._lock:
            return {
                'total': len(self.operations),
                'successful': len([op for op in self.operations if op.success]),
                'failed': len([op for op in self.operations if not op.success]),
                'pending': len([op for op in self.operations if not hasattr(op, 'success')])
            }
    
    def rollback_failed_operations(self) -> int:
        """Rollback all failed operations that support rollback"""
        with self._lock:
            failed_ops = self.get_failed_operations()
            rollback_count = 0
            
            # Rollback in reverse order (LIFO)
            for operation in reversed(failed_ops):
                if operation.can_rollback():
                    if operation.rollback():
                        rollback_count += 1
            
            return rollback_count
    
    def rollback_all_operations(self) -> int:
        """Rollback all operations (for cleanup on failure)"""
        with self._lock:
            rollback_count = 0
            
            # Rollback in reverse order (LIFO)
            for operation in reversed(self.operations):
                if operation.can_rollback():
                    if operation.rollback():
                        rollback_count += 1
            
            return rollback_count
    
    def clear(self) -> None:
        """Clear all tracked operations"""
        with self._lock:
            self.operations.clear()
            self._operation_counter = 0
    
    def get_summary_report(self) -> str:
        """Get human-readable summary report"""
        with self._lock:
            counts = self.get_operation_count()
            failed_ops = self.get_failed_operations()
            
            report = f"Operation Summary:\n"
            report += f"  Total operations: {counts['total']}\n"
            report += f"  Successful: {counts['successful']}\n"
            report += f"  Failed: {counts['failed']}\n"
            
            if failed_ops:
                report += f"\nFailed Operations:\n"
                for op in failed_ops:
                    report += f"  - {op.description}: {op.error_message}\n"
            
            return report
    
    def get_legacy_response_list(self) -> List[int]:
        """Get legacy-style response list (0 for success, non-zero for failure)"""
        with self._lock:
            return [op.get_legacy_exit_code() for op in self.operations]
    
    def set_comprehensive_log_file(self, log_file: Path) -> None:
        """Set comprehensive log file path (like legacy creation.log)"""
        with self._lock:
            self.comprehensive_log_file = log_file
    
    def execute_system_command(
        self, 
        command: Union[str, List[str]], 
        log_context: Optional[str] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None
    ) -> str:
        """
        Execute system command with comprehensive logging (like legacy os_system)
        
        This method provides centralized command execution similar to legacy os_system()
        with automatic operation tracking, logging, and error handling.
        """
        with self._lock:
            # Create operation for this command
            operation_id = self.start_operation(
                OperationType.COMMAND_EXECUTE,
                f"Execute command: {command}" if isinstance(command, str) else f"Execute command: {' '.join(command)}"
            )
            
            operation = self._find_operation(operation_id)
            if operation:
                command_str = command if isinstance(command, str) else ' '.join(command)
                operation.set_command_info(command_str, log_context)
                
                # Write command to comprehensive log if available
                if self.comprehensive_log_file and log_context:
                    self._write_to_log(f"\n-- {log_context}:")
                    self._write_to_log(command_str)
                    self._write_to_log("")
                
                try:
                    # Execute command
                    if isinstance(command, str):
                        # Redirect output to log file if available
                        if self.comprehensive_log_file:
                            result = subprocess.run(
                                f"{command} >> {self.comprehensive_log_file} 2>&1",
                                shell=True,
                                capture_output=False,
                                timeout=timeout,
                                cwd=cwd
                            )
                        else:
                            result = subprocess.run(
                                command,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=timeout,
                                cwd=cwd
                            )
                    else:
                        result = subprocess.run(
                            command,
                            capture_output=True,
                            text=True,
                            timeout=timeout,
                            cwd=cwd
                        )
                    
                    # Record exit status in legacy-compatible list
                    self._response_list.append(result.returncode)
                    
                    if result.returncode == 0:
                        # Success
                        output = getattr(result, 'stdout', '') or ''
                        operation.mark_success(
                            result_data=result,
                            exit_code=result.returncode,
                            output=output
                        )
                        return operation_id
                    else:
                        # Failure - handle like legacy system
                        error_output = getattr(result, 'stderr', '') or ''
                        error_msg = f"Command failed with exit code {result.returncode}"
                        
                        operation.mark_failure(
                            error_message=error_msg,
                            exit_code=result.returncode,
                            output=error_output
                        )
                        
                        # Print error like legacy system
                        print(f"* ERROR: cyris: Issue when executing command (exit status = {result.returncode}):")
                        print(f"  {command_str}")
                        if self.comprehensive_log_file:
                            print(f"  Check the log file for details: {self.comprehensive_log_file}")
                        
                        # Return operation_id for tracking, but don't quit like legacy
                        return operation_id
                        
                except subprocess.TimeoutExpired:
                    error_msg = f"Command timed out after {timeout} seconds"
                    operation.mark_failure(error_msg, exit_code=-1)
                    self._response_list.append(1)
                    print(f"* ERROR: cyris: {error_msg}:")
                    print(f"  {command_str}")
                    return operation_id
                    
                except Exception as e:
                    error_msg = f"Command execution failed: {str(e)}"
                    operation.mark_failure(error_msg, exit_code=-1)
                    self._response_list.append(1)
                    print(f"* ERROR: cyris: {error_msg}:")
                    print(f"  {command_str}")
                    return operation_id
            
            return operation_id
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status like legacy success/failure determination"""
        with self._lock:
            failed_ops = self.get_failed_operations()
            successful_ops = self.get_successful_operations()
            
            # Legacy-style failure count - check both response_list and failed operations
            fail_count = len(failed_ops)
            response_fail_count = len([code for code in self._response_list if code != 0])
            
            # Use the higher count for accuracy
            actual_fail_count = max(fail_count, response_fail_count)
            
            status = {
                'overall_success': actual_fail_count == 0,
                'fail_count': actual_fail_count,
                'total_operations': len(self.operations),
                'successful_operations': len(successful_ops),
                'failed_operations': len(failed_ops),
                'response_list': self._response_list.copy(),
                'creation_status': 'SUCCESS' if actual_fail_count == 0 else 'FAILURE'
            }
            
            return status
    
    def _find_operation(self, operation_id: str) -> Optional[AtomicOperation]:
        """Find operation by ID"""
        for operation in self.operations:
            if operation.operation_id == operation_id:
                return operation
        return None
    
    def _write_to_log(self, message: str) -> None:
        """Write message to comprehensive log file"""
        if self.comprehensive_log_file:
            try:
                with open(self.comprehensive_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"{message}\n")
            except Exception as e:
                logging.error(f"Failed to write to log file {self.comprehensive_log_file}: {e}")


# Global operation tracker instance (similar to legacy RESPONSE_LIST)
GLOBAL_OPERATION_TRACKER = AtomicOperationTracker()


def start_operation(
    operation_type: OperationType, 
    description: str,
    rollback_function: Optional[Callable] = None
) -> str:
    """Convenience function to start tracking an operation globally"""
    return GLOBAL_OPERATION_TRACKER.start_operation(operation_type, description, rollback_function)


def complete_operation(operation_id: str, result_data: Any = None) -> bool:
    """Convenience function to complete an operation"""
    return GLOBAL_OPERATION_TRACKER.complete_operation(operation_id, result_data)


def fail_operation(operation_id: str, error_message: str) -> bool:
    """Convenience function to fail an operation"""
    return GLOBAL_OPERATION_TRACKER.fail_operation(operation_id, error_message)


def is_all_operations_successful() -> bool:
    """Convenience function to check if all operations are successful"""
    return GLOBAL_OPERATION_TRACKER.is_all_successful()


def get_operation_summary() -> str:
    """Convenience function to get operation summary report"""
    return GLOBAL_OPERATION_TRACKER.get_summary_report()


def rollback_on_failure() -> int:
    """Convenience function to rollback failed operations"""
    return GLOBAL_OPERATION_TRACKER.rollback_failed_operations()


def clear_operation_history() -> None:
    """Convenience function to clear operation history"""
    GLOBAL_OPERATION_TRACKER.clear()


def get_legacy_responses() -> List[int]:
    """Convenience function to get legacy-style response codes"""
    return GLOBAL_OPERATION_TRACKER.get_legacy_response_list()


# Enhanced convenience functions for comprehensive logging

def set_comprehensive_log_file(log_file: Union[str, Path]) -> None:
    """Set comprehensive log file for all operations"""
    GLOBAL_OPERATION_TRACKER.set_comprehensive_log_file(Path(log_file))


def execute_command(
    command: Union[str, List[str]], 
    log_context: Optional[str] = None,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None
) -> str:
    """Execute command with comprehensive logging (like legacy os_system)"""
    return GLOBAL_OPERATION_TRACKER.execute_system_command(command, log_context, timeout, cwd)


def get_comprehensive_status() -> Dict[str, Any]:
    """Get comprehensive operation status"""
    return GLOBAL_OPERATION_TRACKER.get_comprehensive_status()


def determine_creation_result() -> Tuple[str, bool]:
    """Determine overall creation result like legacy system"""
    status = get_comprehensive_status()
    result_str = status['creation_status']
    success = status['overall_success']
    return result_str, success


def write_status_file(status_file: Union[str, Path]) -> None:
    """Write creation status to file like legacy system"""
    result_str, success = determine_creation_result()
    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            f.write(f"{result_str}\n")
    except Exception as e:
        logging.error(f"Failed to write status file {status_file}: {e}")


def handle_error_and_quit() -> None:
    """Handle error like legacy system (print error and quit)"""
    status = get_comprehensive_status()
    if not status['overall_success']:
        failed_ops = GLOBAL_OPERATION_TRACKER.get_failed_operations()
        print("* ERROR: cyris: Operation failed")
        for op in failed_ops:
            if op.error_message:
                print(f"  {op.description}: {op.error_message}")
        
        # In legacy system, this would call quit(-1)
        # For modern system, we'll raise an exception instead
        from ..exceptions import CyRISException, CyRISErrorCode
        raise CyRISException(
            f"Operation failed with {status['fail_count']} errors",
            CyRISErrorCode.ORCHESTRATOR_ERROR
        )