"""
Enhanced Command Execution Framework

Provides centralized command execution with comprehensive pre/post logging,
audit trail generation, and integration with the operation tracking system.
Similar to legacy os_system but with modern architecture and enhanced features.
"""

import subprocess
import shlex
import os
from pathlib import Path
from typing import Union, List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .operation_tracker import (
    GLOBAL_OPERATION_TRACKER, OperationType, 
    set_comprehensive_log_file, execute_command
)


@dataclass
class CommandResult:
    """Result of command execution with comprehensive information"""
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    operation_id: Optional[str] = None
    success: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        self.success = self.exit_code == 0


class EnhancedCommandExecutor:
    """
    Enhanced command executor with comprehensive logging
    
    Provides centralized command execution similar to legacy os_system() but with
    structured logging, audit trails, and modern error handling capabilities.
    """
    
    def __init__(self, log_file: Optional[Union[str, Path]] = None):
        """Initialize command executor with optional log file"""
        self.log_file = Path(log_file) if log_file else None
        if self.log_file:
            set_comprehensive_log_file(self.log_file)
        
        # Command execution statistics
        self.commands_executed = 0
        self.commands_successful = 0
        self.commands_failed = 0
    
    def execute(
        self,
        command: Union[str, List[str]],
        log_context: Optional[str] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        capture_output: bool = True,
        shell: bool = True
    ) -> CommandResult:
        """
        Execute command with comprehensive logging
        
        Args:
            command: Command to execute (string or list)
            log_context: Context header for logging (e.g., "Setup SSH keys command")
            timeout: Command timeout in seconds
            cwd: Working directory for command execution
            capture_output: Whether to capture command output
            shell: Whether to use shell for execution
            
        Returns:
            CommandResult with execution details
        """
        start_time = datetime.now()
        command_str = command if isinstance(command, str) else ' '.join(command)
        
        # Track command execution
        self.commands_executed += 1
        
        # Use global operation tracker for centralized tracking
        operation_id = execute_command(command, log_context, timeout, cwd)
        
        # Get operation result from tracker
        operation = GLOBAL_OPERATION_TRACKER._find_operation(operation_id)
        if operation:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            result = CommandResult(
                command=command_str,
                exit_code=operation.exit_code or 0,
                stdout=operation.output or "",
                stderr=operation.error_message or "",
                execution_time=execution_time,
                operation_id=operation_id,
                timestamp=start_time
            )
            
            if result.success:
                self.commands_successful += 1
            else:
                self.commands_failed += 1
            
            return result
        else:
            # Fallback if operation tracking fails
            return CommandResult(
                command=command_str,
                exit_code=1,
                stderr="Failed to track operation",
                execution_time=0.0,
                timestamp=start_time
            )
    
    def execute_with_retry(
        self,
        command: Union[str, List[str]],
        max_retries: int = 3,
        log_context: Optional[str] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None
    ) -> CommandResult:
        """
        Execute command with automatic retry on failure
        
        Args:
            command: Command to execute
            max_retries: Maximum number of retry attempts
            log_context: Context header for logging
            timeout: Command timeout in seconds
            cwd: Working directory for command execution
            
        Returns:
            CommandResult from the last attempt
        """
        last_result = None
        command_str = command if isinstance(command, str) else ' '.join(command)
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Add retry context to logging
                retry_context = f"{log_context} (retry {attempt}/{max_retries})" if log_context else f"Retry {attempt}/{max_retries}"
            else:
                retry_context = log_context
            
            result = self.execute(command, retry_context, timeout, cwd)
            last_result = result
            
            if result.success:
                if attempt > 0:
                    print(f"* INFO: cyris: Command succeeded after {attempt} retries: {command_str}")
                return result
            else:
                if attempt < max_retries:
                    print(f"* WARNING: cyris: Command failed (attempt {attempt + 1}/{max_retries + 1}): {command_str}")
                    print(f"  Exit code: {result.exit_code}, Error: {result.stderr}")
        
        # All attempts failed
        print(f"* ERROR: cyris: Command failed after {max_retries} retries: {command_str}")
        return last_result
    
    def execute_batch(
        self,
        commands: List[Dict[str, Any]],
        stop_on_failure: bool = True
    ) -> List[CommandResult]:
        """
        Execute batch of commands with comprehensive logging
        
        Args:
            commands: List of command dictionaries with keys: 'command', 'log_context', etc.
            stop_on_failure: Whether to stop execution on first failure
            
        Returns:
            List of CommandResult objects
        """
        results = []
        
        print(f"* INFO: cyris: Executing batch of {len(commands)} commands")
        
        for i, cmd_config in enumerate(commands):
            command = cmd_config.get('command')
            if not command:
                continue
                
            log_context = cmd_config.get('log_context', f"Batch command {i+1}")
            timeout = cmd_config.get('timeout')
            cwd = cmd_config.get('cwd')
            
            print(f"* INFO: cyris: Executing command {i+1}/{len(commands)}: {log_context}")
            
            result = self.execute(command, log_context, timeout, cwd)
            results.append(result)
            
            if not result.success and stop_on_failure:
                print(f"* ERROR: cyris: Batch execution stopped due to failure at command {i+1}")
                break
        
        successful = len([r for r in results if r.success])
        failed = len([r for r in results if not r.success])
        
        print(f"* INFO: cyris: Batch execution completed: {successful} successful, {failed} failed")
        
        return results
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get command execution statistics"""
        return {
            'commands_executed': self.commands_executed,
            'commands_successful': self.commands_successful,
            'commands_failed': self.commands_failed,
            'success_rate': (self.commands_successful / max(self.commands_executed, 1)) * 100,
            'log_file': str(self.log_file) if self.log_file else None
        }
    
    def validate_command_safety(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Validate command for basic safety (prevent obvious dangerous operations)
        
        Args:
            command: Command string to validate
            
        Returns:
            Tuple of (is_safe, reason) where reason is provided if unsafe
        """
        # Basic safety checks (can be extended)
        dangerous_patterns = [
            'rm -rf /',
            'mkfs',
            'dd if=/dev/zero',
            '> /dev/sd',
            'chmod 777 /',
            'chown -R'
        ]
        
        command_lower = command.lower().strip()
        
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return False, f"Command contains potentially dangerous pattern: {pattern}"
        
        # Check for unquoted paths with spaces (common source of errors)
        if ' ' in command and not ('"' in command or "'" in command):
            # This is a heuristic - might need refinement
            parts = command.split()
            for part in parts:
                if '/' in part and ' ' in part:
                    return False, f"Unquoted path with spaces detected: {part}"
        
        return True, None
    
    def execute_safe(
        self,
        command: Union[str, List[str]],
        log_context: Optional[str] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        validate_safety: bool = True
    ) -> CommandResult:
        """
        Execute command with safety validation
        
        Args:
            command: Command to execute
            log_context: Context header for logging
            timeout: Command timeout in seconds
            cwd: Working directory for command execution
            validate_safety: Whether to perform safety validation
            
        Returns:
            CommandResult with execution details
        """
        command_str = command if isinstance(command, str) else ' '.join(command)
        
        # Safety validation
        if validate_safety:
            is_safe, reason = self.validate_command_safety(command_str)
            if not is_safe:
                print(f"* ERROR: cyris: Command rejected for safety: {reason}")
                print(f"  Command: {command_str}")
                return CommandResult(
                    command=command_str,
                    exit_code=1,
                    stderr=f"Command rejected for safety: {reason}",
                    execution_time=0.0
                )
        
        return self.execute(command, log_context, timeout, cwd)


# Global command executor instance for convenience
GLOBAL_COMMAND_EXECUTOR = EnhancedCommandExecutor()


def execute_command_safe(
    command: Union[str, List[str]],
    log_context: Optional[str] = None,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None
) -> CommandResult:
    """Convenience function for safe command execution"""
    return GLOBAL_COMMAND_EXECUTOR.execute_safe(command, log_context, timeout, cwd)


def execute_command_with_retry(
    command: Union[str, List[str]],
    max_retries: int = 3,
    log_context: Optional[str] = None,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None
) -> CommandResult:
    """Convenience function for command execution with retry"""
    return GLOBAL_COMMAND_EXECUTOR.execute_with_retry(command, max_retries, log_context, timeout, cwd)


def set_global_log_file(log_file: Union[str, Path]) -> None:
    """Set log file for global command executor"""
    GLOBAL_COMMAND_EXECUTOR.log_file = Path(log_file)
    set_comprehensive_log_file(log_file)


def get_execution_statistics() -> Dict[str, Any]:
    """Get global command execution statistics"""
    return GLOBAL_COMMAND_EXECUTOR.get_execution_statistics()