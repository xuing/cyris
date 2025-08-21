"""
Range Orchestrator Service

This service orchestrates the creation, management, and destruction of cyber ranges.
It coordinates between infrastructure providers, configuration management, and
monitoring services.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass, field
from enum import Enum

from ..config.settings import CyRISSettings
from ..domain.entities.host import Host
from ..domain.entities.guest import Guest


class RangeStatus(Enum):
    """Status of a cyber range instance"""
    CREATING = "creating"
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DESTROYED = "destroyed"


@dataclass
class RangeMetadata:
    """Metadata for a cyber range instance"""
    range_id: str
    name: str
    description: str
    created_at: datetime
    status: RangeStatus = RangeStatus.CREATING
    last_modified: datetime = field(default_factory=datetime.now)
    owner: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    config_path: Optional[str] = None
    logs_path: Optional[str] = None
    
    def update_status(self, status: RangeStatus) -> None:
        """Update range status and last modified time"""
        self.status = status
        self.last_modified = datetime.now()


class InfrastructureProvider(Protocol):
    """Protocol for infrastructure providers (KVM, AWS, etc.)"""
    
    def create_hosts(self, hosts: List[Host]) -> List[str]:
        """Create physical hosts, return host IDs"""
        ...
    
    def create_guests(self, guests: List[Guest], host_mapping: Dict[str, str]) -> List[str]:
        """Create virtual machines, return guest IDs"""
        ...
    
    def destroy_hosts(self, host_ids: List[str]) -> None:
        """Destroy physical hosts"""
        ...
    
    def destroy_guests(self, guest_ids: List[str]) -> None:
        """Destroy virtual machines"""
        ...
    
    def get_status(self, resource_ids: List[str]) -> Dict[str, str]:
        """Get status of resources"""
        ...


class RangeOrchestrator:
    """
    Main orchestrator service for cyber range operations.
    
    This service coordinates the entire lifecycle of cyber ranges:
    - Creation and configuration
    - Status monitoring
    - Resource management
    - Cleanup and destruction
    
    Follows SOLID principles:
    - Single Responsibility: Orchestrates range operations
    - Open/Closed: Extensible via provider interfaces
    - Liskov Substitution: Works with any infrastructure provider
    - Interface Segregation: Focused protocols
    - Dependency Inversion: Depends on abstractions
    """
    
    def __init__(
        self, 
        settings: CyRISSettings,
        infrastructure_provider: InfrastructureProvider,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the orchestrator.
        
        Args:
            settings: CyRIS configuration settings
            infrastructure_provider: Provider for infrastructure operations
            logger: Optional logger instance
        """
        self.settings = settings
        self.provider = infrastructure_provider
        self.logger = logger or logging.getLogger(__name__)
        
        # In-memory range registry (in production, would use persistent storage)
        self._ranges: Dict[str, RangeMetadata] = {}
        self._range_resources: Dict[str, Dict[str, List[str]]] = {}
        
        # Create cyber_range directory if it doesn't exist
        self.ranges_dir = Path(self.settings.cyber_range_dir)
        self.ranges_dir.mkdir(exist_ok=True)
        
        self.logger.info("RangeOrchestrator initialized")
    
    def create_range(
        self,
        range_id: str,
        name: str,
        description: str,
        hosts: List[Host],
        guests: List[Guest],
        owner: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> RangeMetadata:
        """
        Create a new cyber range instance.
        
        Args:
            range_id: Unique identifier for the range
            name: Human-readable name
            description: Range description
            hosts: List of host configurations
            guests: List of guest VM configurations
            owner: Optional owner identifier
            tags: Optional metadata tags
        
        Returns:
            RangeMetadata for the created range
            
        Raises:
            ValueError: If range_id already exists
            RuntimeError: If creation fails
        """
        if range_id in self._ranges:
            raise ValueError(f"Range {range_id} already exists")
        
        self.logger.info(f"Creating range {range_id}: {name}")
        
        # Create range metadata
        metadata = RangeMetadata(
            range_id=range_id,
            name=name,
            description=description,
            created_at=datetime.now(),
            owner=owner,
            tags=tags or {}
        )
        
        try:
            # Register range immediately
            self._ranges[range_id] = metadata
            self._range_resources[range_id] = {"hosts": [], "guests": []}
            
            # Create range directory
            range_dir = self.ranges_dir / range_id
            range_dir.mkdir(exist_ok=True)
            metadata.logs_path = str(range_dir / "logs")
            Path(metadata.logs_path).mkdir(exist_ok=True)
            
            # Create infrastructure resources
            self.logger.info(f"Creating {len(hosts)} hosts for range {range_id}")
            host_ids = self.provider.create_hosts(hosts)
            self._range_resources[range_id]["hosts"] = host_ids
            
            # Create host mapping for guest creation
            host_mapping = {}
            for i, host in enumerate(hosts):
                if i < len(host_ids):
                    host_mapping[host.id] = host_ids[i]
            
            self.logger.info(f"Creating {len(guests)} guests for range {range_id}")
            guest_ids = self.provider.create_guests(guests, host_mapping)
            self._range_resources[range_id]["guests"] = guest_ids
            
            # Update status to active
            metadata.update_status(RangeStatus.ACTIVE)
            
            self.logger.info(f"Successfully created range {range_id}")
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to create range {range_id}: {e}")
            
            # Update status to error
            metadata.update_status(RangeStatus.ERROR)
            
            # Attempt cleanup of partial resources
            try:
                self._cleanup_range_resources(range_id)
            except Exception as cleanup_error:
                self.logger.error(f"Cleanup failed for range {range_id}: {cleanup_error}")
            
            raise RuntimeError(f"Range creation failed: {e}") from e
    
    def get_range(self, range_id: str) -> Optional[RangeMetadata]:
        """Get range metadata by ID"""
        return self._ranges.get(range_id)
    
    def list_ranges(
        self, 
        owner: Optional[str] = None,
        status: Optional[RangeStatus] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[RangeMetadata]:
        """
        List ranges with optional filtering.
        
        Args:
            owner: Filter by owner
            status: Filter by status
            tags: Filter by tags (all must match)
        
        Returns:
            List of matching range metadata
        """
        ranges = list(self._ranges.values())
        
        if owner:
            ranges = [r for r in ranges if r.owner == owner]
        
        if status:
            ranges = [r for r in ranges if r.status == status]
        
        if tags:
            ranges = [
                r for r in ranges 
                if all(r.tags.get(k) == v for k, v in tags.items())
            ]
        
        return ranges
    
    def update_range_status(self, range_id: str) -> Optional[RangeStatus]:
        """
        Update and return the current status of a range.
        
        Args:
            range_id: Range identifier
        
        Returns:
            Current range status or None if not found
        """
        metadata = self._ranges.get(range_id)
        if not metadata:
            return None
        
        try:
            # Get resource IDs
            resources = self._range_resources.get(range_id, {})
            all_resource_ids = resources.get("hosts", []) + resources.get("guests", [])
            
            if not all_resource_ids:
                return metadata.status
            
            # Check infrastructure status
            statuses = self.provider.get_status(all_resource_ids)
            
            # Determine overall status
            if all(status == "active" for status in statuses.values()):
                new_status = RangeStatus.ACTIVE
            elif any(status == "error" for status in statuses.values()):
                new_status = RangeStatus.ERROR
            elif all(status in ["stopped", "terminated"] for status in statuses.values()):
                new_status = RangeStatus.STOPPED
            else:
                new_status = RangeStatus.CREATING  # Mixed states, still creating
            
            if new_status != metadata.status:
                metadata.update_status(new_status)
                self.logger.info(f"Range {range_id} status updated to {new_status.value}")
            
            return new_status
            
        except Exception as e:
            self.logger.error(f"Failed to update status for range {range_id}: {e}")
            metadata.update_status(RangeStatus.ERROR)
            return RangeStatus.ERROR
    
    def destroy_range(self, range_id: str) -> bool:
        """
        Destroy a cyber range and all its resources.
        
        Args:
            range_id: Range identifier
        
        Returns:
            True if successful, False otherwise
        """
        metadata = self._ranges.get(range_id)
        if not metadata:
            self.logger.warning(f"Range {range_id} not found")
            return False
        
        self.logger.info(f"Destroying range {range_id}: {metadata.name}")
        
        try:
            # Update status
            metadata.update_status(RangeStatus.STOPPING)
            
            # Cleanup infrastructure resources
            self._cleanup_range_resources(range_id)
            
            # Update final status
            metadata.update_status(RangeStatus.DESTROYED)
            
            self.logger.info(f"Successfully destroyed range {range_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to destroy range {range_id}: {e}")
            metadata.update_status(RangeStatus.ERROR)
            return False
    
    def _cleanup_range_resources(self, range_id: str) -> None:
        """Clean up infrastructure resources for a range"""
        resources = self._range_resources.get(range_id, {})
        
        # Destroy guests first
        guest_ids = resources.get("guests", [])
        if guest_ids:
            self.logger.info(f"Destroying {len(guest_ids)} guests for range {range_id}")
            self.provider.destroy_guests(guest_ids)
        
        # Then destroy hosts
        host_ids = resources.get("hosts", [])
        if host_ids:
            self.logger.info(f"Destroying {len(host_ids)} hosts for range {range_id}")
            self.provider.destroy_hosts(host_ids)
        
        # Clear resource tracking
        self._range_resources[range_id] = {"hosts": [], "guests": []}
    
    def get_range_resources(self, range_id: str) -> Optional[Dict[str, List[str]]]:
        """Get resource IDs for a range"""
        return self._range_resources.get(range_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        status_counts = {}
        for status in RangeStatus:
            status_counts[status.value] = len([
                r for r in self._ranges.values() if r.status == status
            ])
        
        return {
            "total_ranges": len(self._ranges),
            "status_distribution": status_counts,
            "oldest_range": min(
                (r.created_at for r in self._ranges.values()), 
                default=None
            ),
            "newest_range": max(
                (r.created_at for r in self._ranges.values()), 
                default=None
            )
        }