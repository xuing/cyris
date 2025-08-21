"""
Test unified exception handling system
测试统一异常处理系统
"""

import pytest
import logging
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.core.exceptions import (
    CyRISException, CyRISConfigurationError, CyRISSecurityError,
    CyRISVirtualizationError, CyRISNetworkError, CyRISResourceError,
    CyRISTaskError, ExceptionHandler, ErrorContext, CyRISErrorCode,
    handle_exception, safe_execute, get_exception_handler
)


class TestCyRISErrorCode:
    """Test error code enum"""
    
    def test_error_code_values(self):
        """Test error code values are in expected ranges"""
        assert 1000 <= CyRISErrorCode.UNKNOWN_ERROR.value <= 1099
        assert 1100 <= CyRISErrorCode.VIRTUALIZATION_ERROR.value <= 1199
        assert 1200 <= CyRISErrorCode.ORCHESTRATOR_ERROR.value <= 1299
        assert 1300 <= CyRISErrorCode.SECURITY_ERROR.value <= 1399
        assert 1400 <= CyRISErrorCode.RESOURCE_ALLOCATION_ERROR.value <= 1499
        assert 1500 <= CyRISErrorCode.SSH_CONNECTION_ERROR.value <= 1599
    
    def test_error_code_uniqueness(self):
        """Test all error codes are unique"""
        values = [code.value for code in CyRISErrorCode]
        assert len(values) == len(set(values))


class TestErrorContext:
    """Test error context dataclass"""
    
    def test_error_context_creation(self):
        """Test creating error context"""
        now = datetime.now()
        context = ErrorContext(
            timestamp=now,
            error_code=CyRISErrorCode.SECURITY_ERROR,
            message="Test error",
            component="test"
        )
        
        assert context.timestamp == now
        assert context.error_code == CyRISErrorCode.SECURITY_ERROR
        assert context.message == "Test error"
        assert context.component == "test"
    
    def test_error_context_to_dict(self):
        """Test converting error context to dictionary"""
        now = datetime.now()
        context = ErrorContext(
            timestamp=now,
            error_code=CyRISErrorCode.NETWORK_ERROR,
            message="Network failure",
            component="network",
            range_id="test-range"
        )
        
        data = context.to_dict()
        
        assert data['timestamp'] == now.isoformat()
        assert data['error_code'] == CyRISErrorCode.NETWORK_ERROR.value
        assert data['message'] == "Network failure"
        assert data['component'] == "network"
        assert data['range_id'] == "test-range"


class TestCyRISException:
    """Test base CyRIS exception"""
    
    def test_basic_exception_creation(self):
        """Test creating basic CyRIS exception"""
        exc = CyRISException("Test error")
        
        assert str(exc) == "Test error"
        assert exc.error_code == CyRISErrorCode.UNKNOWN_ERROR
        assert exc.component == "unknown"
        assert exc.error_context.message == "Test error"
    
    def test_exception_with_details(self):
        """Test creating exception with detailed context"""
        exc = CyRISException(
            message="Detailed error",
            error_code=CyRISErrorCode.TASK_EXECUTION_ERROR,
            component="task_executor",
            operation="execute_task",
            range_id="range-123",
            guest_id="guest-456",
            additional_data={"task_type": "add_account"}
        )
        
        assert exc.error_code == CyRISErrorCode.TASK_EXECUTION_ERROR
        assert exc.component == "task_executor"
        assert exc.error_context.operation == "execute_task"
        assert exc.error_context.range_id == "range-123"
        assert exc.error_context.guest_id == "guest-456"
        assert exc.error_context.additional_data["task_type"] == "add_account"
    
    def test_exception_to_dict(self):
        """Test converting exception to dictionary"""
        exc = CyRISException(
            "Convert test",
            error_code=CyRISErrorCode.CONFIGURATION_ERROR,
            component="config"
        )
        
        data = exc.to_dict()
        
        assert data['error_code'] == CyRISErrorCode.CONFIGURATION_ERROR.value
        assert data['message'] == "Convert test"
        assert data['component'] == "config"


class TestSpecificExceptions:
    """Test specific exception types"""
    
    def test_configuration_error(self):
        """Test configuration error exception"""
        exc = CyRISConfigurationError("Config invalid")
        
        assert exc.error_code == CyRISErrorCode.CONFIGURATION_ERROR
        assert exc.component == "configuration"
        assert str(exc) == "Config invalid"
    
    def test_security_error(self):
        """Test security error exception"""
        exc = CyRISSecurityError("Security breach", operation="user_auth")
        
        assert exc.error_code == CyRISErrorCode.SECURITY_ERROR
        assert exc.component == "security"
        assert exc.error_context.operation == "user_auth"
    
    def test_virtualization_error(self):
        """Test virtualization error exception"""
        exc = CyRISVirtualizationError("VM failed")
        
        assert exc.error_code == CyRISErrorCode.VIRTUALIZATION_ERROR
        assert exc.component == "virtualization"
    
    def test_network_error(self):
        """Test network error exception"""
        exc = CyRISNetworkError("Connection timeout")
        
        assert exc.error_code == CyRISErrorCode.NETWORK_ERROR
        assert exc.component == "network"
    
    def test_resource_error(self):
        """Test resource error exception"""
        exc = CyRISResourceError("Out of memory")
        
        assert exc.error_code == CyRISErrorCode.RESOURCE_ALLOCATION_ERROR
        assert exc.component == "resources"
    
    def test_task_error(self):
        """Test task error exception"""
        exc = CyRISTaskError("Task failed")
        
        assert exc.error_code == CyRISErrorCode.TASK_EXECUTION_ERROR
        assert exc.component == "task_executor"


class TestExceptionHandler:
    """Test exception handler"""
    
    def test_handler_creation(self):
        """Test creating exception handler"""
        logger = Mock(spec=logging.Logger)
        handler = ExceptionHandler(logger)
        
        assert handler.logger == logger
        assert len(handler.error_handlers) == 0
        assert len(handler.error_counts) == 0
    
    def test_register_custom_handler(self):
        """Test registering custom exception handler"""
        handler = ExceptionHandler()
        custom_handler = Mock()
        
        handler.register_handler(ValueError, custom_handler)
        
        assert ValueError in handler.error_handlers
        assert handler.error_handlers[ValueError] == custom_handler
    
    def test_handle_cyris_exception(self):
        """Test handling CyRIS exception"""
        logger = Mock(spec=logging.Logger)
        handler = ExceptionHandler(logger)
        
        exc = CyRISSecurityError("Security test")
        context = handler.handle_exception(exc)
        
        assert context is not None
        assert context.error_code == CyRISErrorCode.SECURITY_ERROR
        assert context.message == "Security test"
        
        # Check error count
        assert handler.error_counts[CyRISErrorCode.SECURITY_ERROR] == 1
        
        # Check logging was called
        assert logger.log.called
    
    def test_handle_generic_exception(self):
        """Test handling generic Python exception"""
        logger = Mock(spec=logging.Logger)
        handler = ExceptionHandler(logger)
        
        exc = ValueError("Generic error")
        context = handler.handle_exception(exc)
        
        assert context is not None
        assert context.error_code == CyRISErrorCode.UNKNOWN_ERROR
        assert "Generic error" in context.message
        
        # Check error count
        assert handler.error_counts[CyRISErrorCode.UNKNOWN_ERROR] == 1
    
    def test_handle_exception_with_reraise(self):
        """Test handling exception with reraise"""
        handler = ExceptionHandler()
        exc = CyRISConfigurationError("Config error")
        
        with pytest.raises(CyRISConfigurationError):
            handler.handle_exception(exc, reraise=True)
        
        # Should still count the error
        assert handler.error_counts[CyRISErrorCode.CONFIGURATION_ERROR] == 1
    
    def test_custom_handler_execution(self):
        """Test custom handler gets called"""
        handler = ExceptionHandler()
        custom_handler = Mock()
        handler.register_handler(ValueError, custom_handler)
        
        exc = ValueError("Test value error")
        handler.handle_exception(exc)
        
        # Custom handler should be called
        assert custom_handler.called
        call_args = custom_handler.call_args[0]
        assert isinstance(call_args[0], CyRISException)
    
    def test_error_statistics(self):
        """Test error statistics tracking"""
        handler = ExceptionHandler()
        
        # Handle different types of errors
        handler.handle_exception(CyRISSecurityError("Security 1"))
        handler.handle_exception(CyRISSecurityError("Security 2"))
        handler.handle_exception(CyRISNetworkError("Network 1"))
        
        stats = handler.get_error_statistics()
        
        assert stats['SECURITY_ERROR'] == 2
        assert stats['NETWORK_ERROR'] == 1
        assert len(stats) == 2
    
    def test_clear_statistics(self):
        """Test clearing error statistics"""
        handler = ExceptionHandler()
        
        handler.handle_exception(CyRISSecurityError("Test"))
        assert len(handler.error_counts) == 1
        
        handler.clear_statistics()
        assert len(handler.error_counts) == 0
    
    def test_log_levels_by_error_type(self):
        """Test different log levels for different error types"""
        logger = Mock(spec=logging.Logger)
        handler = ExceptionHandler(logger)
        
        # Security error should be CRITICAL
        handler.handle_exception(CyRISSecurityError("Security issue"))
        assert logger.log.call_args[0][0] == logging.CRITICAL
        
        # Infrastructure error should be ERROR
        handler.handle_exception(CyRISVirtualizationError("VM issue"))
        assert logger.log.call_args[0][0] == logging.ERROR
        
        # General error should be WARNING
        handler.handle_exception(CyRISConfigurationError("Config issue"))
        assert logger.log.call_args[0][0] == logging.WARNING


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_global_exception_handler(self):
        """Test global exception handler access"""
        handler = get_exception_handler()
        assert isinstance(handler, ExceptionHandler)
        
        # Should be same instance
        handler2 = get_exception_handler()
        assert handler is handler2
    
    def test_handle_exception_function(self):
        """Test convenience handle_exception function"""
        exc = CyRISTaskError("Task failed")
        context = handle_exception(exc)
        
        assert context is not None
        assert context.error_code == CyRISErrorCode.TASK_EXECUTION_ERROR
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function"""
        def success_func(x, y):
            return x + y
        
        result = safe_execute(success_func, 5, 10)
        assert result == 15
    
    def test_safe_execute_with_exception(self):
        """Test safe_execute with function that raises exception"""
        def failing_func():
            raise ValueError("Function failed")
        
        result = safe_execute(failing_func, default_return="default")
        assert result == "default"
    
    def test_safe_execute_with_context(self):
        """Test safe_execute with context information"""
        def failing_func():
            raise CyRISNetworkError("Network issue")
        
        logger = Mock(spec=logging.Logger)
        result = safe_execute(
            failing_func,
            context={"operation": "test"},
            default_return=None,
            logger=logger
        )
        
        assert result is None
        # Logger should have been used
        assert logger.log.called


class TestExceptionHandlerIntegration:
    """Integration tests for exception handler"""
    
    def test_handler_with_real_logger(self, caplog):
        """Test exception handler with real logger"""
        with caplog.at_level(logging.WARNING):
            handler = ExceptionHandler()
            exc = CyRISConfigurationError("Real config error")
            handler.handle_exception(exc)
        
        # Check log was captured
        assert "CONFIGURATION_ERROR" in caplog.text
        assert "Real config error" in caplog.text
    
    def test_exception_chaining(self):
        """Test exception chaining with causes"""
        original_exc = ValueError("Original error")
        
        try:
            raise original_exc
        except ValueError as e:
            cyris_exc = CyRISTaskError("Wrapped error", cause=e)
            
        assert cyris_exc.cause == original_exc
        assert str(cyris_exc) == "Wrapped error"
    
    def test_handler_error_recovery(self):
        """Test handler gracefully handles its own errors"""
        handler = ExceptionHandler()
        
        # Register a handler that raises an exception
        def failing_handler(exc, context):
            raise RuntimeError("Handler failed")
        
        handler.register_handler(ValueError, failing_handler)
        
        # This should not crash
        context = handler.handle_exception(ValueError("Test error"))
        assert context is not None


@pytest.fixture
def temp_dir(tmp_path):
    """Temporary directory fixture for tests"""
    return tmp_path