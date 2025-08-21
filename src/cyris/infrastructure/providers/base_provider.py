"""
Base Infrastructure Provider

This module defines the abstract interface for infrastructure providers,
ensuring consistent API across different virtualization and cloud platforms.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum

from ...domain.entities.host import Host
from ...domain.entities.guest import Guest


class ResourceStatus(Enum):
    """Status of infrastructure resources"""
    CREATING = "creating"
    ACTIVE = "active"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class ResourceInfo:
    """Information about an infrastructure resource"""
    resource_id: str
    resource_type: str  # "host", "guest", "network", "storage"
    name: str
    status: ResourceStatus
    metadata: Dict[str, Any]
    created_at: Optional[str] = None
    ip_addresses: Optional[List[str]] = None
    tags: Optional[Dict[str, str]] = None


class NetworkProvider(Protocol):
    """Protocol for network management operations"""
    
    def create_network(self, network_name: str, cidr: str, **kwargs) -> str:
        """Create a network, return network ID"""
        ...
    
    def create_bridge(self, bridge_name: str, **kwargs) -> str:
        """Create a network bridge, return bridge ID"""
        ...
    
    def delete_network(self, network_id: str) -> None:
        """Delete a network"""
        ...
    
    def delete_bridge(self, bridge_id: str) -> None:
        """Delete a network bridge"""
        ...
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """List all networks"""
        ...


class StorageProvider(Protocol):
    """Protocol for storage management operations"""
    
    def create_volume(self, size_gb: int, name: str, **kwargs) -> str:
        """Create a storage volume, return volume ID"""
        ...
    
    def delete_volume(self, volume_id: str) -> None:
        """Delete a storage volume"""
        ...
    
    def attach_volume(self, volume_id: str, instance_id: str, device: str = None) -> None:
        """Attach volume to instance"""
        ...
    
    def detach_volume(self, volume_id: str, instance_id: str) -> None:
        """Detach volume from instance"""
        ...


class InfrastructureProvider(ABC):
    """
    Abstract base class for infrastructure providers.
    
    This interface defines the contract that all infrastructure providers
    must implement, ensuring consistent operations across different platforms.
    
    Follows SOLID principles:
    - Interface Segregation: Focused on core infrastructure operations
    - Dependency Inversion: Clients depend on this abstraction, not concrete implementations
    - Liskov Substitution: All implementations must be substitutable
    """
    
    def __init__(self, provider_name: str, config: Dict[str, Any]):
        """
        Initialize the infrastructure provider.
        
        Args:
            provider_name: Name of the provider (e.g., "kvm", "aws")
            config: Provider-specific configuration
        """
        self.provider_name = provider_name
        self.config = config
        self._resources: Dict[str, ResourceInfo] = {}
    
    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the infrastructure provider.
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Clean up and close connections"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if provider is connected and ready"""
        pass
    
    @abstractmethod
    def create_hosts(self, hosts: List[Host]) -> List[str]:
        """
        Create physical hosts or host-level infrastructure.
        
        Args:
            hosts: List of host configurations
        
        Returns:
            List of created host resource IDs
        
        Raises:
            InfrastructureError: If creation fails
        """
        pass
    
    @abstractmethod
    def create_guests(self, guests: List[Guest], host_mapping: Dict[str, str]) -> List[str]:
        """
        Create virtual machines or guest instances.
        
        Args:
            guests: List of guest configurations
            host_mapping: Mapping of guest host references to actual host IDs
        
        Returns:
            List of created guest resource IDs
        
        Raises:
            InfrastructureError: If creation fails
        """
        pass
    
    @abstractmethod
    def destroy_hosts(self, host_ids: List[str]) -> None:
        """
        Destroy physical hosts or host-level infrastructure.
        
        Args:
            host_ids: List of host resource IDs to destroy
        
        Raises:
            InfrastructureError: If destruction fails
        """
        pass
    
    @abstractmethod
    def destroy_guests(self, guest_ids: List[str]) -> None:
        """
        Destroy virtual machines or guest instances.
        
        Args:
            guest_ids: List of guest resource IDs to destroy
        
        Raises:
            InfrastructureError: If destruction fails
        """
        pass
    
    @abstractmethod
    def get_status(self, resource_ids: List[str]) -> Dict[str, str]:
        """
        Get status of resources.
        
        Args:
            resource_ids: List of resource IDs to check
        
        Returns:
            Dictionary mapping resource ID to status string
        
        Raises:
            InfrastructureError: If status check fails
        """
        pass
    
    @abstractmethod
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """
        Get detailed information about a resource.
        
        Args:
            resource_id: Resource identifier
        
        Returns:
            ResourceInfo object or None if not found
        """
        pass
    
    def list_resources(
        self, 
        resource_type: Optional[str] = None,
        status: Optional[ResourceStatus] = None
    ) -> List[ResourceInfo]:
        """
        List all resources managed by this provider.
        
        Args:
            resource_type: Filter by resource type (optional)
            status: Filter by status (optional)
        
        Returns:
            List of matching resources
        """
        resources = list(self._resources.values())
        
        if resource_type:
            resources = [r for r in resources if r.resource_type == resource_type]
        
        if status:
            resources = [r for r in resources if r.status == status]
        
        return resources
    
    def validate_configuration(self) -> List[str]:
        """
        Validate provider configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.provider_name:
            errors.append("Provider name is required")
        
        if not isinstance(self.config, dict):
            errors.append("Configuration must be a dictionary")
        
        return errors
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the provider"""
        return {
            "provider_name": self.provider_name,
            "connected": self.is_connected(),
            "total_resources": len(self._resources),
            "resource_types": list(set(r.resource_type for r in self._resources.values())),
            "config_keys": list(self.config.keys()) if self.config else []
        }
    
    def _register_resource(self, resource_info: ResourceInfo) -> None:
        """Register a resource in the internal registry"""
        self._resources[resource_info.resource_id] = resource_info
    
    def _unregister_resource(self, resource_id: str) -> None:
        """Remove a resource from the internal registry"""
        self._resources.pop(resource_id, None)
    
    def _update_resource_status(self, resource_id: str, status: ResourceStatus) -> None:
        """Update status of a registered resource"""
        if resource_id in self._resources:
            self._resources[resource_id].status = status


class InfrastructureError(Exception):
    """Base exception for infrastructure operations"""
    
    def __init__(self, message: str, provider: str = None, resource_id: str = None):
        """
        Initialize infrastructure error.
        
        Args:
            message: Error message
            provider: Provider name (optional)
            resource_id: Resource ID that caused the error (optional)
        """
        super().__init__(message)
        self.provider = provider
        self.resource_id = resource_id
    
    def __str__(self):
        parts = [self.args[0]]
        if self.provider:
            parts.append(f"Provider: {self.provider}")
        if self.resource_id:
            parts.append(f"Resource: {self.resource_id}")
        return " | ".join(parts)


class ConnectionError(InfrastructureError):
    """Error connecting to infrastructure provider"""
    pass


class ResourceCreationError(InfrastructureError):
    """Error creating infrastructure resources"""
    pass


class ResourceDestructionError(InfrastructureError):
    """Error destroying infrastructure resources"""
    pass


class ResourceNotFoundError(InfrastructureError):
    """Resource not found error"""
    pass