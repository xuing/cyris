"""
Comprehensive Log Aggregation System

Provides centralized log file management similar to legacy creation.log with
structured log entry formatting, cross-service log correlation, and
comprehensive audit trail generation for each cyber range.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, TextIO
from dataclasses import dataclass, field
from enum import Enum
import threading
import logging


class LogLevel(Enum):
    """Log levels for comprehensive logging"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Individual log entry with comprehensive metadata"""
    timestamp: datetime
    level: LogLevel
    source: str  # Module/service that generated the log
    operation_id: Optional[str]
    message: str
    context: Optional[Dict[str, Any]] = None
    command: Optional[str] = None
    exit_code: Optional[int] = None
    
    def to_legacy_format(self) -> str:
        """Format log entry in legacy style"""
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        level_prefix = f"* {self.level.value}: cyris:"
        
        if self.command:
            return f"[{timestamp_str}] {level_prefix} Executing: {self.command}"
        else:
            return f"[{timestamp_str}] {level_prefix} {self.message}"
    
    def to_detailed_format(self) -> str:
        """Format log entry with detailed information"""
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        entry = f"[{timestamp_str}] [{self.level.value}] [{self.source}]"
        
        if self.operation_id:
            entry += f" [OP:{self.operation_id}]"
        
        entry += f" {self.message}"
        
        if self.command:
            entry += f"\n  Command: {self.command}"
        
        if self.exit_code is not None:
            entry += f"\n  Exit Code: {self.exit_code}"
        
        if self.context:
            entry += f"\n  Context: {json.dumps(self.context, indent=2)}"
        
        return entry


class ComprehensiveLogAggregator:
    """
    Comprehensive log aggregation system
    
    Similar to legacy creation.log but with enhanced structure, cross-service
    correlation, and modern logging capabilities while maintaining the single
    comprehensive log file approach.
    """
    
    def __init__(self, range_id: str, base_log_dir: Union[str, Path] = "/var/cyris/ranges"):
        """
        Initialize log aggregator for a specific range
        
        Args:
            range_id: Unique identifier for the cyber range
            base_log_dir: Base directory for range logs
        """
        self.range_id = range_id
        self.base_log_dir = Path(base_log_dir)
        self.range_log_dir = self.base_log_dir / range_id
        self.creation_log_file = self.range_log_dir / "creation.log"
        self.detailed_log_file = self.range_log_dir / "detailed.log"
        self.status_file = self.range_log_dir / "cr_creation_status"
        
        # In-memory log storage for fast access
        self.log_entries: List[LogEntry] = []
        self._lock = threading.RLock()
        
        # Operation tracking
        self.operation_contexts: Dict[str, Dict[str, Any]] = {}
        self.operation_sequence: List[str] = []
        
        # Statistics
        self.stats = {
            'total_entries': 0,
            'entries_by_level': {level.value: 0 for level in LogLevel},
            'entries_by_source': {},
            'commands_executed': 0,
            'operations_tracked': 0
        }
        
        self._ensure_log_directory()
        self._initialize_log_files()
    
    def _ensure_log_directory(self) -> None:
        """Ensure log directory exists"""
        try:
            self.range_log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create log directory {self.range_log_dir}: {e}")
    
    def _initialize_log_files(self) -> None:
        """Initialize log files with headers"""
        try:
            # Initialize creation.log in legacy format
            with open(self.creation_log_file, 'w', encoding='utf-8') as f:
                f.write(f"CyRIS Range Creation Log - {self.range_id}\n")
                f.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
            
            # Initialize detailed.log with structured format
            with open(self.detailed_log_file, 'w', encoding='utf-8') as f:
                f.write(f"CyRIS Detailed Operation Log - {self.range_id}\n")
                f.write(f"Started at: {datetime.now().isoformat()}\n")
                f.write("=" * 100 + "\n\n")
        
        except Exception as e:
            logging.error(f"Failed to initialize log files: {e}")
    
    def log(
        self,
        level: LogLevel,
        message: str,
        source: str = "cyris",
        operation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        command: Optional[str] = None,
        exit_code: Optional[int] = None
    ) -> None:
        """
        Add log entry to comprehensive logging system
        
        Args:
            level: Log level
            message: Log message
            source: Source module/service
            operation_id: Optional operation ID for correlation
            context: Additional context information
            command: Command being executed (if applicable)
            exit_code: Exit code (if applicable)
        """
        with self._lock:
            entry = LogEntry(
                timestamp=datetime.now(),
                level=level,
                source=source,
                operation_id=operation_id,
                message=message,
                context=context,
                command=command,
                exit_code=exit_code
            )
            
            # Store in memory
            self.log_entries.append(entry)
            
            # Update statistics
            self.stats['total_entries'] += 1
            self.stats['entries_by_level'][level.value] += 1
            self.stats['entries_by_source'][source] = self.stats['entries_by_source'].get(source, 0) + 1
            
            if command:
                self.stats['commands_executed'] += 1
            
            if operation_id and operation_id not in self.operation_sequence:
                self.operation_sequence.append(operation_id)
                self.stats['operations_tracked'] += 1
            
            # Write to log files
            self._write_to_creation_log(entry)
            self._write_to_detailed_log(entry)
    
    def _write_to_creation_log(self, entry: LogEntry) -> None:
        """Write entry to legacy-style creation.log"""
        try:
            with open(self.creation_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{entry.to_legacy_format()}\n")
        except Exception as e:
            logging.error(f"Failed to write to creation.log: {e}")
    
    def _write_to_detailed_log(self, entry: LogEntry) -> None:
        """Write entry to detailed structured log"""
        try:
            with open(self.detailed_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{entry.to_detailed_format()}\n\n")
        except Exception as e:
            logging.error(f"Failed to write to detailed.log: {e}")
    
    def start_operation_context(self, operation_id: str, operation_type: str, description: str) -> None:
        """Start a new operation context for log correlation"""
        with self._lock:
            self.operation_contexts[operation_id] = {
                'operation_type': operation_type,
                'description': description,
                'start_time': datetime.now(),
                'entries': []
            }
            
            # Log operation start
            self.log(
                LogLevel.INFO,
                f"Starting operation: {description}",
                operation_id=operation_id,
                context={'operation_type': operation_type}
            )
    
    def end_operation_context(self, operation_id: str, success: bool, result_message: Optional[str] = None) -> None:
        """End an operation context"""
        with self._lock:
            if operation_id in self.operation_contexts:
                context = self.operation_contexts[operation_id]
                context['end_time'] = datetime.now()
                context['success'] = success
                context['duration'] = (context['end_time'] - context['start_time']).total_seconds()
                
                level = LogLevel.INFO if success else LogLevel.ERROR
                message = result_message or ("Operation completed successfully" if success else "Operation failed")
                
                self.log(
                    level,
                    f"Completed operation: {context['description']} - {message}",
                    operation_id=operation_id,
                    context={
                        'operation_type': context['operation_type'],
                        'duration': context['duration'],
                        'success': success
                    }
                )
    
    def log_command_execution(
        self,
        command: str,
        log_context: str,
        operation_id: Optional[str] = None
    ) -> None:
        """Log command execution in legacy style"""
        with self._lock:
            # Write command context header (like legacy)
            self.log(
                LogLevel.INFO,
                f"\n-- {log_context}:",
                operation_id=operation_id
            )
            
            # Write actual command
            self.log(
                LogLevel.INFO,
                command,
                command=command,
                operation_id=operation_id
            )
    
    def log_command_result(
        self,
        command: str,
        exit_code: int,
        output: Optional[str] = None,
        operation_id: Optional[str] = None
    ) -> None:
        """Log command execution result"""
        with self._lock:
            if exit_code == 0:
                self.log(
                    LogLevel.INFO,
                    f"Command completed successfully",
                    command=command,
                    exit_code=exit_code,
                    operation_id=operation_id
                )
            else:
                self.log(
                    LogLevel.ERROR,
                    f"Command failed with exit code {exit_code}",
                    command=command,
                    exit_code=exit_code,
                    operation_id=operation_id,
                    context={'output': output} if output else None
                )
    
    def get_operation_summary(self) -> Dict[str, Any]:
        """Get summary of all operations"""
        with self._lock:
            summary = {
                'range_id': self.range_id,
                'total_operations': len(self.operation_contexts),
                'successful_operations': len([ctx for ctx in self.operation_contexts.values() if ctx.get('success', False)]),
                'failed_operations': len([ctx for ctx in self.operation_contexts.values() if not ctx.get('success', True)]),
                'operation_sequence': self.operation_sequence.copy(),
                'statistics': self.stats.copy(),
                'log_files': {
                    'creation_log': str(self.creation_log_file),
                    'detailed_log': str(self.detailed_log_file),
                    'status_file': str(self.status_file)
                }
            }
            return summary
    
    def write_final_status(self, overall_success: bool, failure_count: int = 0) -> None:
        """Write final creation status like legacy system"""
        try:
            # Write to status file
            status_str = "SUCCESS" if overall_success else "FAILURE"
            with open(self.status_file, 'w', encoding='utf-8') as f:
                f.write(f"{status_str}\n")
            
            # Write final summary to logs
            duration = "unknown"
            if self.log_entries:
                start_time = self.log_entries[0].timestamp
                end_time = self.log_entries[-1].timestamp
                duration = f"{(end_time - start_time).total_seconds():.1f}s"
            
            final_message = f"Creation result: {status_str}"
            if failure_count > 0:
                final_message += f" ({failure_count} errors)"
            final_message += f" (took {duration})"
            
            self.log(LogLevel.INFO, final_message)
            
            # Write operation summary
            summary = self.get_operation_summary()
            self.log(
                LogLevel.INFO,
                f"Operation Summary: {summary['successful_operations']} successful, {summary['failed_operations']} failed",
                context=summary
            )
            
        except Exception as e:
            logging.error(f"Failed to write final status: {e}")
    
    def get_log_entries_by_level(self, level: LogLevel) -> List[LogEntry]:
        """Get all log entries of specified level"""
        with self._lock:
            return [entry for entry in self.log_entries if entry.level == level]
    
    def get_log_entries_by_operation(self, operation_id: str) -> List[LogEntry]:
        """Get all log entries for specific operation"""
        with self._lock:
            return [entry for entry in self.log_entries if entry.operation_id == operation_id]
    
    def export_logs_to_json(self, output_file: Union[str, Path]) -> None:
        """Export all logs to JSON format for external processing"""
        with self._lock:
            try:
                export_data = {
                    'range_id': self.range_id,
                    'export_time': datetime.now().isoformat(),
                    'summary': self.get_operation_summary(),
                    'entries': [
                        {
                            'timestamp': entry.timestamp.isoformat(),
                            'level': entry.level.value,
                            'source': entry.source,
                            'operation_id': entry.operation_id,
                            'message': entry.message,
                            'context': entry.context,
                            'command': entry.command,
                            'exit_code': entry.exit_code
                        }
                        for entry in self.log_entries
                    ]
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)
                    
            except Exception as e:
                logging.error(f"Failed to export logs to JSON: {e}")


# Global log aggregators for active ranges
_active_aggregators: Dict[str, ComprehensiveLogAggregator] = {}
_aggregators_lock = threading.RLock()


def get_range_log_aggregator(range_id: str, base_log_dir: Union[str, Path] = "/var/cyris/ranges") -> ComprehensiveLogAggregator:
    """Get or create log aggregator for a range"""
    with _aggregators_lock:
        if range_id not in _active_aggregators:
            _active_aggregators[range_id] = ComprehensiveLogAggregator(range_id, base_log_dir)
        return _active_aggregators[range_id]


def log_to_range(
    range_id: str,
    level: LogLevel,
    message: str,
    source: str = "cyris",
    operation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    command: Optional[str] = None,
    exit_code: Optional[int] = None
) -> None:
    """Convenience function to log to specific range"""
    aggregator = get_range_log_aggregator(range_id)
    aggregator.log(level, message, source, operation_id, context, command, exit_code)


def finalize_range_logging(range_id: str, overall_success: bool, failure_count: int = 0) -> None:
    """Finalize logging for a range and write status files"""
    with _aggregators_lock:
        if range_id in _active_aggregators:
            aggregator = _active_aggregators[range_id]
            aggregator.write_final_status(overall_success, failure_count)
            # Keep aggregator active for potential queries