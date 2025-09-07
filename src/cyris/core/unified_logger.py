"""
Unified Logging System

Provides centralized logger factory and formatting to replace all print() and scattered 
logging usage throughout CyRIS. Maintains backward compatibility with existing log 
formats while providing structured, consistent logging.

Features:
- Unified logger factory with consistent configuration
- Multiple output formats (legacy, structured, rich)
- Automatic file and console handlers
- Context-aware logging with operation tracking
- Performance optimizations and thread safety
"""

import os
import sys
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any, Union, TextIO, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json

# Thread-local storage for logger contexts
_logger_context = threading.local()

# Global project root path detection
def _get_project_root() -> Path:
    """Automatically detect CyRIS project root directory"""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / 'pyproject.toml').exists() and (parent / 'CLAUDE.md').exists():
            return parent
    # Fallback to /home/ubuntu/cyris if detection fails
    return Path('/home/ubuntu/cyris')

# Project-wide log directory configuration
_PROJECT_ROOT = _get_project_root()
_PROJECT_LOG_DIR = _PROJECT_ROOT / 'logs'


class LogFormat(Enum):
    """Supported log output formats"""
    LEGACY = "legacy"      # [2025-09-05 02:26:35] * INFO: cyris: message
    STRUCTURED = "structured"  # [2025-09-05 02:26:35.150] [INFO] [component] message
    JSON = "json"          # {"timestamp": "...", "level": "INFO", "message": "..."}
    SIMPLE = "simple"      # INFO: message (for console)


@dataclass
class LoggerConfig:
    """Configuration for unified logger"""
    # Basic configuration
    name: str
    level: int = logging.INFO
    format_type: LogFormat = LogFormat.STRUCTURED
    
    # File output configuration  
    file_path: Optional[Path] = None
    file_level: int = logging.DEBUG
    file_format: LogFormat = LogFormat.STRUCTURED
    
    # Console output configuration
    console_enabled: bool = True
    console_level: int = logging.INFO
    console_format: LogFormat = LogFormat.SIMPLE
    
    # Context and metadata
    component: Optional[str] = None
    operation_id: Optional[str] = None
    range_id: Optional[str] = None
    
    # Advanced options
    enable_rich_output: bool = False
    enable_context_tracking: bool = True
    thread_safe: bool = True


class LoggerFormatter(logging.Formatter):
    """Custom formatter supporting multiple output formats"""
    
    def __init__(self, format_type: LogFormat, component: Optional[str] = None):
        self.format_type = format_type
        self.component = component
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record based on configured format type"""
        # Add context information from thread-local storage
        context = getattr(_logger_context, 'context', {})
        
        if self.format_type == LogFormat.LEGACY:
            return self._format_legacy(record, context)
        elif self.format_type == LogFormat.STRUCTURED:
            return self._format_structured(record, context)
        elif self.format_type == LogFormat.JSON:
            return self._format_json(record, context)
        elif self.format_type == LogFormat.SIMPLE:
            return self._format_simple(record, context)
        else:
            return super().format(record)
    
    def _format_legacy(self, record: logging.LogRecord, context: Dict) -> str:
        """Format: [2025-09-05 02:26:35] * INFO: cyris: message"""
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] * {record.levelname}: cyris: {record.getMessage()}"
    
    def _format_structured(self, record: logging.LogRecord, context: Dict) -> str:
        """Format: [2025-09-05 02:26:35.150] [INFO] [component] message"""
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        component = self.component or context.get('component', record.name.split('.')[-1])
        
        message = record.getMessage()
        
        # Add operation context if available
        op_id = context.get('operation_id')
        if op_id:
            message = f"[OP:{op_id}] {message}"
        
        base_msg = f"[{timestamp}] [{record.levelname}] [{component}] {message}"
        
        # Add context block if available
        if context.get('metadata'):
            context_json = json.dumps(context['metadata'], indent=2)
            base_msg += f"\n  Context: {context_json}"
        
        return base_msg
    
    def _format_json(self, record: logging.LogRecord, context: Dict) -> str:
        """Format: JSON structured logging"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'component': self.component or record.name,
            'message': record.getMessage(),
            'logger': record.name,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add context data
        log_data.update(context)
        
        return json.dumps(log_data, ensure_ascii=False)
    
    def _format_simple(self, record: logging.LogRecord, context: Dict) -> str:
        """Format: INFO: message (for console)"""
        return f"{record.levelname}: {record.getMessage()}"


class UnifiedLogger:
    """
    Unified logger implementation with context support and multiple output formats.
    Replaces print() statements and provides consistent logging across CyRIS.
    """
    
    def __init__(self, config: LoggerConfig):
        self.config = config
        self.logger = logging.getLogger(config.name)
        self.logger.setLevel(config.level)
        
        # Clear existing handlers to avoid duplication
        self.logger.handlers.clear()
        self.logger.propagate = False
        
        self._setup_handlers()
        
        # Store config for context
        self._component = config.component
        self._operation_id = config.operation_id
        self._range_id = config.range_id
    
    def _setup_handlers(self):
        """Set up file and console handlers with appropriate formatters"""
        
        # File handler
        if self.config.file_path:
            file_handler = logging.FileHandler(
                self.config.file_path, 
                mode='a', 
                encoding='utf-8'
            )
            file_handler.setLevel(self.config.file_level)
            file_formatter = LoggerFormatter(
                self.config.file_format, 
                self.config.component
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # Console handler
        if self.config.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.config.console_level)
            console_formatter = LoggerFormatter(
                self.config.console_format,
                self.config.component
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def set_context(self, **kwargs):
        """Set logging context for current thread"""
        if not hasattr(_logger_context, 'context'):
            _logger_context.context = {}
        
        _logger_context.context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context for current thread"""
        _logger_context.context = {}
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Internal method to log with context"""
        # Temporarily set context
        old_context = getattr(_logger_context, 'context', {}).copy()
        
        try:
            # Merge provided context with existing
            current_context = old_context.copy()
            if kwargs:
                current_context['metadata'] = kwargs
            
            # Add configured context
            if self._component:
                current_context['component'] = self._component
            if self._operation_id:
                current_context['operation_id'] = self._operation_id
            if self._range_id:
                current_context['range_id'] = self._range_id
            
            _logger_context.context = current_context
            
            # Log the message
            self.logger.log(level, message)
            
        finally:
            # Restore original context
            _logger_context.context = old_context


class LoggerFactory:
    """
    Centralized logger factory to replace all print() and logging.getLogger() usage.
    Provides consistent configuration and formatting across all CyRIS modules.
    """
    
    _loggers: Dict[str, UnifiedLogger] = {}
    _default_config: Optional[LoggerConfig] = None
    _lock = threading.Lock()
    
    @classmethod
    def set_default_config(cls, config: LoggerConfig):
        """Set default logger configuration for all new loggers"""
        with cls._lock:
            cls._default_config = config
    
    @classmethod
    def get_logger(
        cls, 
        name: str, 
        component: Optional[str] = None,
        config: Optional[LoggerConfig] = None
    ) -> UnifiedLogger:
        """
        Get or create a unified logger for a specific component.
        
        Args:
            name: Logger name (typically __name__)
            component: Component name for logging context
            config: Optional custom configuration
        
        Returns:
            UnifiedLogger instance
        """
        with cls._lock:
            cache_key = f"{name}:{component or ''}"
            
            if cache_key not in cls._loggers:
                # Create configuration
                if config is None:
                    if cls._default_config is None:
                        # Create default config
                        config = LoggerConfig(
                            name=name,
                            component=component or name.split('.')[-1]
                        )
                    else:
                        # Use default config as base
                        config = LoggerConfig(
                            name=name,
                            level=cls._default_config.level,
                            format_type=cls._default_config.format_type,
                            file_path=cls._default_config.file_path,
                            file_level=cls._default_config.file_level,
                            file_format=cls._default_config.file_format,
                            console_enabled=cls._default_config.console_enabled,
                            console_level=cls._default_config.console_level,
                            console_format=cls._default_config.console_format,
                            component=component or cls._default_config.component,
                            operation_id=cls._default_config.operation_id,
                            range_id=cls._default_config.range_id,
                            enable_rich_output=cls._default_config.enable_rich_output,
                            enable_context_tracking=cls._default_config.enable_context_tracking,
                            thread_safe=cls._default_config.thread_safe
                        )
                
                # Create logger
                logger = UnifiedLogger(config)
                cls._loggers[cache_key] = logger
            
            return cls._loggers[cache_key]
    
    @classmethod
    def create_range_logger(
        cls, 
        range_id: str, 
        component: str,
        log_dir: Optional[Path] = None
    ) -> UnifiedLogger:
        """
        Create a logger specifically for a cyber range operation.
        
        Args:
            range_id: Range identifier
            component: Component name
            log_dir: Directory for log files
        
        Returns:
            UnifiedLogger configured for range operations
        """
        logger_name = f"cyris.range.{range_id}.{component}"
        
        # Determine log file path
        if log_dir:
            creation_log = log_dir / "creation.log"
            detailed_log = log_dir / "detailed.log"
        else:
            creation_log = None
            detailed_log = None
        
        config = LoggerConfig(
            name=logger_name,
            component=component,
            range_id=range_id,
            file_path=detailed_log,  # Use detailed log for structured format
            file_format=LogFormat.STRUCTURED,
            console_format=LogFormat.SIMPLE,
            enable_context_tracking=True
        )
        
        logger = UnifiedLogger(config)
        
        # Add legacy format handler for creation.log if needed
        if creation_log:
            legacy_handler = logging.FileHandler(creation_log, mode='a', encoding='utf-8')
            legacy_handler.setLevel(logging.INFO)
            legacy_formatter = LoggerFormatter(LogFormat.LEGACY)
            legacy_handler.setFormatter(legacy_formatter)
            logger.logger.addHandler(legacy_handler)
        
        return logger
    
    @classmethod
    def configure_for_range_operation(
        cls,
        range_id: str,
        operation_id: str,
        log_dir: Path
    ):
        """
        Configure all loggers for a specific range operation.
        This should be called at the start of range creation/destruction.
        """
        default_config = LoggerConfig(
            name="cyris",
            component="cyris",
            range_id=range_id,
            operation_id=operation_id,
            file_path=log_dir / "detailed.log",
            file_format=LogFormat.STRUCTURED,
            console_format=LogFormat.SIMPLE
        )
        
        cls.set_default_config(default_config)
    
    @classmethod
    def reset(cls):
        """Reset logger factory (useful for testing)"""
        with cls._lock:
            cls._loggers.clear()
            cls._default_config = None


# Convenience functions to replace print() usage
def get_logger(name: str, component: Optional[str] = None) -> UnifiedLogger:
    """Convenience function to get a logger - replaces logging.getLogger()"""
    return LoggerFactory.get_logger(name, component)


def get_project_log_path(log_name: str, subdir: Optional[str] = None) -> Path:
    """
    Get standardized log file path within project logs directory.
    
    Args:
        log_name: Name of the log file (e.g., 'debug_main.log')
        subdir: Optional subdirectory (e.g., 'main', 'infrastructure', 'debug')
    
    Returns:
        Path: Full path to the log file within project logs directory
    """
    # Ensure logs directory exists
    if subdir:
        log_dir = _PROJECT_LOG_DIR / subdir
    else:
        log_dir = _PROJECT_LOG_DIR
    
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / log_name


def get_main_debug_log_path() -> Path:
    """Get path for main debug log file"""
    return get_project_log_path('debug_main.log', 'main')


def get_parser_debug_log_path() -> Path:
    """Get path for parser debug log file"""  
    return get_project_log_path('debug_parser.log', 'main')


def get_virt_install_debug_log_path() -> Path:
    """Get path for virt-install debug log file"""
    return get_project_log_path('debug_virt_install.log', 'infrastructure')


def get_creation_log_path(suffix: str = '') -> Path:
    """Get path for creation log files"""
    log_name = f'create{suffix}.log' if suffix else 'create.log'
    return get_project_log_path(log_name, 'operations')


def print_replacement(*args, **kwargs) -> None:
    """
    Replacement for print() statements. 
    
    This should be used during refactoring to maintain the same interface
    while routing output through the logging system.
    """
    # Convert print arguments to string
    message = ' '.join(str(arg) for arg in args)
    
    # Get a default logger
    logger = LoggerFactory.get_logger("cyris.print", "print")
    logger.info(message)


# Context managers for temporary logging configuration
class LoggingContext:
    """Context manager for temporary logging configuration"""
    
    def __init__(self, **context_kwargs):
        self.context_kwargs = context_kwargs
        self.old_context = {}
    
    def __enter__(self):
        # Store old context
        if hasattr(_logger_context, 'context'):
            self.old_context = _logger_context.context.copy()
        else:
            _logger_context.context = {}
        
        # Set new context
        _logger_context.context.update(self.context_kwargs)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old context
        _logger_context.context = self.old_context


class RangeLoggingContext(LoggingContext):
    """Specialized context manager for range operations"""
    
    def __init__(self, range_id: str, operation_id: str, component: str = "cyris"):
        super().__init__(
            range_id=range_id,
            operation_id=operation_id,
            component=component
        )