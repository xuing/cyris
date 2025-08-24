"""
Unified Exception Handling System for CyRIS

This module provides centralized exception handling, error codes,
and consistent error reporting throughout the CyRIS system.
"""

import logging
import traceback
from enum import Enum, unique
from typing import Dict, Any, Optional, Union, Type
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@unique
class CyRISErrorCode(Enum):
    """Standardized error codes for CyRIS system"""
    
    # General errors (1000-1099)
    UNKNOWN_ERROR = 1000
    VALIDATION_ERROR = 1001
    CONFIGURATION_ERROR = 1002
    PERMISSION_ERROR = 1003
    
    # Infrastructure errors (1100-1199)
    VIRTUALIZATION_ERROR = 1100
    NETWORK_ERROR = 1101
    STORAGE_ERROR = 1102
    PROVIDER_ERROR = 1103
    
    # Service errors (1200-1299) 
    ORCHESTRATOR_ERROR = 1200
    TASK_EXECUTION_ERROR = 1201
    MONITORING_ERROR = 1202
    CLEANUP_ERROR = 1203
    
    # Security errors (1300-1399)
    SECURITY_ERROR = 1300
    AUTHENTICATION_ERROR = 1301
    AUTHORIZATION_ERROR = 1302
    COMMAND_INJECTION_ERROR = 1303
    
    # Resource management errors (1400-1499)
    RESOURCE_ALLOCATION_ERROR = 1400
    RESOURCE_CLEANUP_ERROR = 1401
    MEMORY_ERROR = 1402
    DISK_SPACE_ERROR = 1403
    
    # Network and connectivity errors (1500-1599)
    SSH_CONNECTION_ERROR = 1500
    NETWORK_TIMEOUT_ERROR = 1501
    DNS_RESOLUTION_ERROR = 1502
    PORT_BINDING_ERROR = 1503
    TUNNEL_ERROR = 1504


@dataclass
class ErrorContext:
    """Context information for errors"""
    timestamp: datetime
    error_code: CyRISErrorCode
    message: str
    component: str
    operation: Optional[str] = None
    user_id: Optional[str] = None
    range_id: Optional[str] = None
    guest_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['error_code'] = self.error_code.value
        return data


class CyRISException(Exception):
    """Base exception class for CyRIS system"""
    
    def __init__(
        self, 
        message: str, 
        error_code: CyRISErrorCode = CyRISErrorCode.UNKNOWN_ERROR,
        component: str = "unknown",
        operation: Optional[str] = None,
        user_id: Optional[str] = None,
        range_id: Optional[str] = None,
        guest_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        
        self.error_context = ErrorContext(
            timestamp=datetime.now(),
            error_code=error_code,
            message=message,
            component=component,
            operation=operation,
            user_id=user_id,
            range_id=range_id,
            guest_id=guest_id,
            additional_data=additional_data or {},
            stack_trace=traceback.format_exc() if cause or traceback.format_exc() != 'NoneType: None\n' else None
        )
        
        self.cause = cause
    
    @property
    def error_code(self) -> CyRISErrorCode:
        return self.error_context.error_code
    
    @property
    def component(self) -> str:
        return self.error_context.component
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return self.error_context.to_dict()


class CyRISConfigurationError(CyRISException):
    """Configuration-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.CONFIGURATION_ERROR,
            component="configuration",
            **kwargs
        )


class CyRISSecurityError(CyRISException):
    """Security-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.SECURITY_ERROR,
            component="security",
            **kwargs
        )


class CyRISVirtualizationError(CyRISException):
    """Virtualization-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.VIRTUALIZATION_ERROR,
            component="virtualization",
            **kwargs
        )


class CyRISNetworkError(CyRISException):
    """Network-related errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.NETWORK_ERROR,
            component="network",
            **kwargs
        )


class CyRISResourceError(CyRISException):
    """Resource management errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.RESOURCE_ALLOCATION_ERROR,
            component="resources",
            **kwargs
        )


class CyRISTaskError(CyRISException):
    """Task execution errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.TASK_EXECUTION_ERROR,
            component="task_executor",
            **kwargs
        )


class TunnelError(CyRISException):
    """SSH tunnel management errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.TUNNEL_ERROR,
            component="tunnel_manager",
            **kwargs
        )


class GatewayError(CyRISException):
    """Gateway service errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=CyRISErrorCode.NETWORK_ERROR,
            component="gateway_service",
            **kwargs
        )


class ExceptionHandler:
    """Centralized exception handler for CyRIS"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_handlers: Dict[Type[Exception], callable] = {}
        self.error_counts: Dict[CyRISErrorCode, int] = {}
    
    def register_handler(self, exception_type: Type[Exception], handler: callable):
        """Register a custom handler for specific exception types"""
        self.error_handlers[exception_type] = handler
    
    def handle_exception(
        self, 
        exception: Exception, 
        context: Optional[Dict[str, Any]] = None,
        reraise: bool = False
    ) -> Optional[ErrorContext]:
        """
        Handle an exception with consistent logging and processing.
        
        Args:
            exception: The exception to handle
            context: Additional context information
            reraise: Whether to re-raise the exception after handling
        
        Returns:
            ErrorContext if exception was handled, None if re-raised
        """
        try:
            # Convert to CyRISException if needed
            if isinstance(exception, CyRISException):
                cyris_exception = exception
            else:
                # Wrap in generic CyRISException
                cyris_exception = CyRISException(
                    message=str(exception),
                    error_code=CyRISErrorCode.UNKNOWN_ERROR,
                    component="unknown",
                    additional_data=context,
                    cause=exception
                )
            
            # Update error counts
            self.error_counts[cyris_exception.error_code] = \
                self.error_counts.get(cyris_exception.error_code, 0) + 1
            
            # Log the exception
            self._log_exception(cyris_exception)
            
            # Call custom handler if registered
            exception_type = type(exception)
            if exception_type in self.error_handlers:
                try:
                    self.error_handlers[exception_type](cyris_exception, context)
                except Exception as handler_error:
                    self.logger.critical(f"Custom handler failed: {handler_error}")
            
            if reraise:
                raise cyris_exception
            
            return cyris_exception.error_context
            
        except Exception as handler_error:
            # Avoid recursion in exception handling
            self.logger.critical(f"Exception handler failed: {handler_error}")
            if reraise:
                raise exception
            
            # Return a basic error context even if handler fails
            return ErrorContext(
                timestamp=datetime.now(),
                error_code=CyRISErrorCode.UNKNOWN_ERROR,
                message=f"Handler failed: {str(handler_error)}",
                component="exception_handler"
            )
    
    def _log_exception(self, exception: CyRISException):
        """Log exception with appropriate level"""
        error_code = exception.error_code
        
        # Determine log level based on error type
        if error_code.value >= 1300:  # Security errors
            log_level = logging.CRITICAL
        elif error_code.value >= 1100:  # Infrastructure errors
            log_level = logging.ERROR
        else:
            log_level = logging.WARNING
        
        log_message = (
            f"[{error_code.name}] {exception.error_context.component}: "
            f"{exception.error_context.message}"
        )
        
        extra_data = {
            'error_code': error_code.value,
            'component': exception.error_context.component,
            'operation': exception.error_context.operation,
            'range_id': exception.error_context.range_id,
            'guest_id': exception.error_context.guest_id,
        }
        
        self.logger.log(log_level, log_message, extra=extra_data)
        
        # Log stack trace at debug level
        if exception.error_context.stack_trace:
            self.logger.debug(f"Stack trace for {error_code.name}: {exception.error_context.stack_trace}")
    
    def get_error_statistics(self) -> Dict[str, int]:
        """Get error statistics"""
        return {error_code.name: count for error_code, count in self.error_counts.items()}
    
    def clear_statistics(self):
        """Clear error statistics"""
        self.error_counts.clear()


# Global exception handler instance
_global_exception_handler = ExceptionHandler()


def get_exception_handler() -> ExceptionHandler:
    """Get the global exception handler instance"""
    return _global_exception_handler


def handle_exception(
    exception: Exception, 
    context: Optional[Dict[str, Any]] = None,
    reraise: bool = False,
    logger: Optional[logging.Logger] = None
) -> Optional[ErrorContext]:
    """
    Convenience function to handle exceptions using the global handler
    
    Args:
        exception: Exception to handle
        context: Additional context information
        reraise: Whether to re-raise after handling
        logger: Optional logger to use
    
    Returns:
        ErrorContext if handled, None if re-raised
    """
    handler = _global_exception_handler
    if logger:
        handler.logger = logger
    
    return handler.handle_exception(exception, context, reraise)


def safe_execute(
    func: callable,
    *args,
    context: Optional[Dict[str, Any]] = None,
    default_return=None,
    logger: Optional[logging.Logger] = None,
    **kwargs
):
    """
    Execute a function with automatic exception handling
    
    Args:
        func: Function to execute
        *args: Positional arguments for function
        context: Context information for error reporting
        default_return: Value to return if exception occurs
        logger: Logger to use for error reporting
        **kwargs: Keyword arguments for function
    
    Returns:
        Function result or default_return if exception occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_exception(e, context=context, logger=logger)
        return default_return