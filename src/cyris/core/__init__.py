"""
Core Module Exports

Exports unified logging system and other core utilities.
"""

from .unified_logger import (
    LoggerFactory,
    LoggerConfig,
    LogFormat,
    UnifiedLogger,
    get_logger,
    print_replacement,
    LoggingContext,
    RangeLoggingContext
)

from .exceptions import (
    CyRISException,
    CyRISVirtualizationError,
    CyRISNetworkError,
    CyRISResourceError,
    GatewayError,
    TunnelError,
    ExceptionHandler,
    handle_exception,
    safe_execute
)

# Provide easy imports for most common usage
__all__ = [
    # Unified logging system
    'LoggerFactory',
    'LoggerConfig', 
    'LogFormat',
    'UnifiedLogger',
    'get_logger',
    'print_replacement',
    'LoggingContext',
    'RangeLoggingContext',
    
    # Exception handling
    'CyRISException',
    'CyRISVirtualizationError', 
    'CyRISNetworkError',
    'CyRISResourceError',
    'GatewayError',
    'TunnelError',
    'ExceptionHandler',
    'handle_exception',
    'safe_execute'
]