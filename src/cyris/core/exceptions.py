"""
Simplified Exception Handling System

Provides essential exception handling following the legacy pattern.
Replaces the over-engineered 399-line version with ~50 lines of focused functionality.

Complexity Reduction: 399 → 50 lines (87% reduction)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CyRISException(Exception):
    """Base exception class for CyRIS system (simplified)"""
    
    def __init__(self, message: str, operation: str = "unknown", **kwargs):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.context = kwargs
        
        # Log error in legacy format
        logger.error(f"* ERROR: cyris: {operation}: {message}")


class CyRISVirtualizationError(CyRISException):
    """Virtualization-related errors"""
    pass


class CyRISNetworkError(CyRISException):
    """Network-related errors"""
    pass


class CyRISResourceError(CyRISException):
    """Resource allocation/cleanup errors"""
    pass


class GatewayError(CyRISException):
    """Gateway and tunnel errors"""
    pass


class TunnelError(CyRISException):
    """Tunnel-specific errors (SSH tunnels, network tunnels)"""
    pass


# Simple exception handler decorator
def handle_exception(func):
    """Simple exception handler decorator"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CyRISException:
            raise  # Re-raise CyRIS exceptions as-is
        except Exception as e:
            logger.error(f"* ERROR: cyris: {func.__name__}: Unexpected error: {e}")
            raise CyRISException(f"Unexpected error in {func.__name__}: {e}", operation=func.__name__)
    return wrapper


# Simple safe execution function (legacy pattern)
def safe_execute(func, *args, context: Optional[Dict[str, Any]] = None, 
                default_return: Any = None, logger: Optional[logging.Logger] = None, **kwargs):
    """Safe function execution with error capture (legacy pattern)"""
    exec_logger = logger or logging.getLogger(__name__)
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        operation = context.get('operation', func.__name__) if context else func.__name__
        exec_logger.error(f"* ERROR: cyris: {operation}: {e}")
        
        if default_return is not None:
            return default_return
        
        raise CyRISException(str(e), operation=operation)


class ExceptionHandler:
    """Simple exception handler (legacy compatibility)"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def handle_error(self, error: Exception, operation: str) -> None:
        """Handle error with legacy-style logging"""
        self.logger.error(f"* ERROR: cyris: {operation}: {error}")
    
    def handle_exception(self, error: Exception, operation: str = "", context: str = "", **kwargs) -> None:
        """Handle exception with legacy-style logging (alias for handle_error)"""
        # Combine operation and context for better error messages
        full_operation = f"{operation} ({context})" if context and operation else (operation or context or "unknown")
        self.handle_error(error, full_operation)
    
    def safe_execute(self, func, *args, **kwargs):
        """Safe execution wrapper"""
        return safe_execute(func, *args, logger=self.logger, **kwargs)