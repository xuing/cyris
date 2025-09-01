"""
Base Automation Provider Interface

Defines the abstract interface for automation tools (Terraform, Packer, etc.)
following the provider pattern used throughout CyRIS infrastructure.
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
import uuid
from datetime import datetime

from ...core.exceptions import CyRISException


class AutomationStatus(Enum):
    """Status enumeration for automation operations"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationError(CyRISException):
    """Base exception for automation-related errors"""
    pass


@dataclass
class AutomationConfig:
    """Base configuration for automation providers"""
    provider_type: str
    enabled: bool = True
    timeout: int = 3600  # 1 hour default
    retry_count: int = 3
    working_directory: Optional[Path] = None
    environment_variables: Dict[str, str] = field(default_factory=dict)
    debug_mode: bool = False


@dataclass 
class AutomationResult:
    """Result of an automation operation"""
    operation_id: str
    provider_type: str
    status: AutomationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error_message: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        """Get operation duration in seconds"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if operation completed successfully"""
        return self.status == AutomationStatus.COMPLETED
    
    @property 
    def is_failed(self) -> bool:
        """Check if operation failed"""
        return self.status == AutomationStatus.FAILED


class AutomationProvider(ABC):
    """
    Abstract base class for automation providers.
    
    Automation providers handle specific tools like Terraform, Packer, or Vagrant
    to automate infrastructure provisioning tasks.
    
    All automation providers must implement:
    - Connection and lifecycle management
    - Operation execution with status tracking
    - Error handling and recovery
    - Artifact management
    """
    
    def __init__(self, config: AutomationConfig):
        """
        Initialize automation provider.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._is_connected = False
        self._active_operations: Dict[str, AutomationResult] = {}
    
    @property
    def provider_type(self) -> str:
        """Get the provider type identifier"""
        return self.config.provider_type
    
    @property
    def is_connected(self) -> bool:
        """Check if provider is connected and ready"""
        return self._is_connected
    
    @property
    def is_enabled(self) -> bool:
        """Check if provider is enabled"""
        return self.config.enabled
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to automation provider and verify availability.
        
        Raises:
            AutomationError: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from automation provider and cleanup resources.
        """
        pass
    
    @abstractmethod
    async def validate_configuration(self) -> List[str]:
        """
        Validate provider configuration and return any issues.
        
        Returns:
            List of validation error messages, empty if valid
        """
        pass
    
    @abstractmethod
    async def execute_operation(
        self, 
        operation_type: str,
        parameters: Dict[str, Any],
        operation_id: Optional[str] = None
    ) -> AutomationResult:
        """
        Execute an automation operation.
        
        Args:
            operation_type: Type of operation (e.g., 'build', 'plan', 'apply')
            parameters: Operation-specific parameters
            operation_id: Optional operation ID for tracking
            
        Returns:
            Result of the automation operation
            
        Raises:
            AutomationError: If operation fails
        """
        pass
    
    @abstractmethod
    async def get_operation_status(self, operation_id: str) -> Optional[AutomationResult]:
        """
        Get status of a specific operation.
        
        Args:
            operation_id: Unique operation identifier
            
        Returns:
            Operation result if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel a running operation.
        
        Args:
            operation_id: Unique operation identifier
            
        Returns:
            True if operation was cancelled, False otherwise
        """
        pass
    
    @abstractmethod
    async def cleanup_artifacts(self, operation_id: str) -> None:
        """
        Clean up artifacts from a completed operation.
        
        Args:
            operation_id: Unique operation identifier
        """
        pass
    
    def generate_operation_id(self) -> str:
        """Generate a unique operation ID"""
        return f"{self.provider_type}-{uuid.uuid4().hex[:8]}"
    
    def _track_operation(self, result: AutomationResult) -> None:
        """Track an active operation"""
        self._active_operations[result.operation_id] = result
    
    def _untrack_operation(self, operation_id: str) -> None:
        """Stop tracking a completed operation"""
        self._active_operations.pop(operation_id, None)
    
    def get_active_operations(self) -> List[AutomationResult]:
        """Get list of all active operations"""
        return list(self._active_operations.values())
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on automation provider.
        
        Returns:
            Health check results including status, version, capabilities
        """
        try:
            if not self.is_connected:
                await self.connect()
            
            validation_issues = await self.validate_configuration()
            
            return {
                'provider_type': self.provider_type,
                'status': 'healthy' if not validation_issues else 'degraded',
                'connected': self.is_connected,
                'enabled': self.is_enabled,
                'active_operations': len(self._active_operations),
                'validation_issues': validation_issues,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'provider_type': self.provider_type,
                'status': 'unhealthy',
                'connected': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def __str__(self) -> str:
        """String representation of provider"""
        return f"{self.__class__.__name__}(type={self.provider_type}, enabled={self.is_enabled})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (
            f"{self.__class__.__name__}("
            f"provider_type='{self.provider_type}', "
            f"enabled={self.is_enabled}, "
            f"connected={self.is_connected}, "
            f"active_operations={len(self._active_operations)}"
            f")"
        )