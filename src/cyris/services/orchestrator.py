"""
Range Orchestrator Service

This service orchestrates the creation, management, and destruction of cyber ranges.
It coordinates between infrastructure providers, configuration management, and
monitoring services.
"""

import logging
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..config.settings import CyRISSettings
from ..infrastructure.network.topology_manager import NetworkTopologyManager
from ..infrastructure.network.tunnel_manager import TunnelManager
from .task_executor import TaskExecutor, TaskResult
from .gateway_service import GatewayService, EntryPointInfo
from ..core.exceptions import (
    ExceptionHandler, CyRISException, CyRISVirtualizationError, 
    CyRISNetworkError, CyRISResourceError, GatewayError, handle_exception, safe_execute
)

# Import both modern and legacy entities for compatibility
from ..domain.entities.host import Host as ModernHost
from ..domain.entities.guest import Guest as ModernGuest

# Import legacy entities for YAML parsing
import sys
import os
legacy_path = os.path.join(os.path.dirname(__file__), '../../..', 'main')
if legacy_path not in sys.path:
    sys.path.insert(0, legacy_path)

try:
    from entities import Host, Guest
except ImportError:
    # Fallback to modern entities if legacy not available
    Host = ModernHost
    Guest = ModernGuest


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['last_modified'] = self.last_modified.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RangeMetadata':
        """Create instance from dictionary"""
        data = data.copy()
        data['status'] = RangeStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        return cls(**data)


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
        
        # Initialize exception handler
        self.exception_handler = ExceptionHandler(self.logger)
        
        try:
            # Initialize network topology and task execution managers
            self.topology_manager = NetworkTopologyManager()
            self.task_executor = TaskExecutor({
                'base_path': settings.cyris_path,
                'ssh_timeout': 30,
                'ssh_retries': 3
            })
            
            # Initialize gateway services (tunnel manager and gateway service)
            self.tunnel_manager = TunnelManager(settings)
            self.gateway_service = GatewayService(settings, self.tunnel_manager)
            
            # Persistent range registry
            self._ranges: Dict[str, RangeMetadata] = {}
            self._range_resources: Dict[str, Dict[str, List[str]]] = {}
            
            # Create cyber_range directory if it doesn't exist
            self.ranges_dir = Path(self.settings.cyber_range_dir)
            self.ranges_dir.mkdir(exist_ok=True)
            
            # Persistent storage files
            self._metadata_file = self.ranges_dir / "ranges_metadata.json"
            self._resources_file = self.ranges_dir / "ranges_resources.json"
            
            # Load existing data from disk
            self._load_persistent_data()
            
            self.logger.info("RangeOrchestrator initialized with unified exception handling")
            
        except Exception as e:
            self.exception_handler.handle_exception(
                e, 
                context={"component": "orchestrator", "operation": "initialization"},
                reraise=True
            )
    
    def create_range(
        self,
        range_id: str,
        name: str,
        description: str,
        hosts: List[Host],
        guests: List[Guest],
        topology_config: Optional[Dict[str, Any]] = None,
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
            raise CyRISVirtualizationError(
                f"Range {range_id} already exists",
                operation="create_range",
                range_id=range_id
            )
        
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
            host_ids = safe_execute(
                self.provider.create_hosts,
                hosts,
                context={
                    "component": "orchestrator",
                    "operation": "create_hosts", 
                    "range_id": range_id
                },
                default_return=[],
                logger=self.logger
            )
            
            if not host_ids:
                raise CyRISVirtualizationError(
                    f"Failed to create hosts for range {range_id}",
                    operation="create_hosts",
                    range_id=range_id
                )
            
            self._range_resources[range_id]["hosts"] = host_ids
            
            # Create host mapping for guest creation
            host_mapping = {}
            for i, host in enumerate(hosts):
                if i < len(host_ids):
                    # Get host ID - legacy Host uses host_id, modern Host uses id
                    host_id = getattr(host, 'id', None) or getattr(host, 'host_id', 'unknown')
                    host_mapping[host_id] = host_ids[i]
            
            self.logger.info(f"Creating {len(guests)} guests for range {range_id}")
            
            # Set current range context in provider for file organization
            old_range_context = getattr(self.provider, '_current_range_id', None)
            self.provider._current_range_id = range_id
            
            try:
                guest_ids = safe_execute(
                    self.provider.create_guests,
                    guests, host_mapping,
                    context={
                        "component": "orchestrator",
                        "operation": "create_guests", 
                        "range_id": range_id
                    },
                    default_return=[],
                    logger=self.logger
                )
            finally:
                # Restore previous range context
                if old_range_context is not None:
                    self.provider._current_range_id = old_range_context
                else:
                    if hasattr(self.provider, '_current_range_id'):
                        delattr(self.provider, '_current_range_id')
            
            if not guest_ids:
                raise CyRISVirtualizationError(
                    f"Failed to create guests for range {range_id}",
                    operation="create_guests",
                    range_id=range_id
                )
            
            self._range_resources[range_id]["guests"] = guest_ids
            
            # Create network topology if specified
            if topology_config:
                self.logger.info(f"Creating network topology for range {range_id}")
                # Connect topology manager to provider's libvirt connection if available
                if hasattr(self.provider, '_connection'):
                    self.topology_manager.libvirt_connection = self.provider._connection
                
                ip_assignments = self.topology_manager.create_topology(
                    topology_config, guests, range_id
                )
                self.logger.info(f"Assigned IPs to {len(ip_assignments)} guests")
                
                # Store IP assignments for later task execution
                metadata.tags['ip_assignments'] = json.dumps(ip_assignments)
            
            # Execute tasks on guests if they have task configurations
            task_results = []
            for guest in guests:
                guest_id = getattr(guest, 'id', None) or getattr(guest, 'guest_id', 'unknown')
                
                # Get IP address for the guest
                guest_ip = None
                if topology_config and hasattr(self.topology_manager, 'ip_assignments'):
                    guest_ip = self.topology_manager.get_guest_ip(guest_id)
                
                # Use predefined IP if available
                if not guest_ip and hasattr(guest, 'ip_addr') and guest.ip_addr:
                    guest_ip = guest.ip_addr
                
                # Execute tasks if guest has them and IP is available
                if guest_ip and hasattr(guest, 'tasks') and guest.tasks:
                    self.logger.info(f"Executing tasks for guest {guest_id} at {guest_ip}")
                    
                    results = safe_execute(
                        self.task_executor.execute_guest_tasks,
                        guest, guest_ip, guest.tasks,
                        context={
                            "component": "orchestrator", 
                            "operation": "execute_guest_tasks",
                            "range_id": range_id,
                            "guest_id": guest_id
                        },
                        default_return=[],
                        logger=self.logger
                    )
                    
                    if results:
                        task_results.extend(results)
                        
                        # Log task results
                        for result in results:
                            if result.success:
                                self.logger.info(f"Task {result.task_id}: {result.message}")
                            else:
                                self.logger.warning(f"Task {result.task_id} failed: {result.message}")
            
            # Store task results in metadata
            if task_results:
                metadata.tags['task_results'] = json.dumps([
                    {
                        'task_id': r.task_id,
                        'task_type': r.task_type.value,
                        'success': r.success,
                        'message': r.message
                    } for r in task_results
                ])
            
            # Update status to active
            metadata.update_status(RangeStatus.ACTIVE)
            
            # Save persistent data
            self._save_persistent_data()
            
            self.logger.info(f"Successfully created range {range_id} with {len(task_results)} tasks executed")
            return metadata
            
        except CyRISException:
            # Re-raise CyRIS exceptions as-is
            raise
        except Exception as e:
            # Handle any other exceptions through unified handler
            self.exception_handler.handle_exception(
                e, 
                context={
                    "component": "orchestrator",
                    "operation": "create_range",
                    "range_id": range_id
                }
            )
            
            # Update status to error
            metadata.update_status(RangeStatus.ERROR)
            
            # Attempt cleanup of partial resources
            safe_execute(
                self._cleanup_range_resources,
                range_id,
                context={"operation": "cleanup_after_failure", "range_id": range_id},
                logger=self.logger
            )
            
            # Save state even on error
            self._save_persistent_data()
            
            raise CyRISVirtualizationError(
                f"Range creation failed: {e}",
                operation="create_range",
                range_id=range_id,
                cause=e
            )
    
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
                self._save_persistent_data()
                self.logger.info(f"Range {range_id} status updated to {new_status.value}")
            
            return new_status
            
        except Exception as e:
            self.logger.error(f"Failed to update status for range {range_id}: {e}")
            metadata.update_status(RangeStatus.ERROR)
            self._save_persistent_data()
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
            
            # Save persistent data
            self._save_persistent_data()
            
            self.logger.info(f"Successfully destroyed range {range_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to destroy range {range_id}: {e}")
            metadata.update_status(RangeStatus.ERROR)
            # Save error state
            self._save_persistent_data()
            return False
    
    def remove_range(self, range_id: str, force: bool = False) -> bool:
        """
        Completely remove a cyber range from the system (metadata and all records).
        
        This operation permanently deletes all traces of a range from the orchestrator.
        By default, only allows removal of destroyed ranges for safety.
        
        Args:
            range_id: Range identifier
            force: If True, allows removal of non-destroyed ranges (dangerous!)
        
        Returns:
            True if successful, False otherwise
        """
        metadata = self._ranges.get(range_id)
        if not metadata:
            self.logger.warning(f"Range {range_id} not found")
            return False
        
        # Safety check: only allow removal of destroyed ranges unless forced
        if not force and metadata.status != RangeStatus.DESTROYED:
            self.logger.error(f"Range {range_id} is not destroyed (status: {metadata.status.value})")
            self.logger.error("Use --force to remove non-destroyed ranges, or destroy first")
            return False
        
        self.logger.info(f"Removing range {range_id}: {metadata.name} (status: {metadata.status.value})")
        
        try:
            # If range is not destroyed, clean up resources first
            if metadata.status != RangeStatus.DESTROYED:
                self.logger.warning(f"Force removing active range {range_id}, cleaning up resources first")
                self._cleanup_range_resources(range_id)
            
            # Remove from memory
            if range_id in self._ranges:
                del self._ranges[range_id]
            
            if range_id in self._range_resources:
                del self._range_resources[range_id]
            
            # Clean up all range-related files and directories
            import shutil
            import glob
            
            # Remove range directory
            range_dir = self.ranges_dir / range_id
            if range_dir.exists():
                self.logger.info(f"Removing range directory: {range_dir}")
                shutil.rmtree(range_dir)
            
            # Remove disk image files - check both old and new locations
            removed_disks = []
            
            # New location: range-specific disks directory
            range_disks_dir = self.ranges_dir / range_id / "disks"
            if range_disks_dir.exists():
                self.logger.info(f"Removing range-specific disk directory: {range_disks_dir}")
                disk_files = list(range_disks_dir.glob("*.qcow2"))
                for disk_file in disk_files:
                    try:
                        disk_file.unlink()
                        removed_disks.append(disk_file.name)
                        self.logger.info(f"Removed disk file: {disk_file.name}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove disk file {disk_file.name}: {e}")
                
                # Remove the disks directory if empty
                try:
                    if not any(range_disks_dir.iterdir()):
                        range_disks_dir.rmdir()
                except:
                    pass
            
            # Legacy location: check root cyber_range directory for old disk files
            cyber_range_dir = self.ranges_dir.parent if self.ranges_dir.name == range_id else self.ranges_dir
            
            # Get range resources to identify which disk files actually belong to this range
            range_resources = self._range_resources.get(range_id, {})
            range_disks = range_resources.get('disks', [])
            
            # Remove tracked disk files from legacy location
            for disk_name in range_disks:
                legacy_disk_path = cyber_range_dir / disk_name
                if legacy_disk_path.exists():
                    try:
                        legacy_disk_path.unlink()
                        removed_disks.append(disk_name)
                        self.logger.info(f"Removed legacy disk file: {disk_name}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove legacy disk file {disk_name}: {e}")
            
            # Also check for any remaining disk files with range ID pattern (fallback)
            disk_pattern = f"*{range_id}*.qcow2"
            pattern_files = glob.glob(str(cyber_range_dir / disk_pattern))
            for disk_file in pattern_files:
                disk_path = Path(disk_file)
                try:
                    disk_path.unlink()
                    removed_disks.append(disk_path.name)
                    self.logger.info(f"Removed pattern-matched disk file: {disk_path.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove pattern-matched disk file {disk_path.name}: {e}")
            
            if removed_disks:
                self.logger.info(f"Removed {len(removed_disks)} disk files total: {', '.join(removed_disks)}")
            
            # Remove network configurations if any
            # This could be extended to clean up libvirt networks, bridges, etc.
            range_networks = range_resources.get('networks', [])
            if range_networks:
                self.logger.info(f"Range had {len(range_networks)} networks, manual cleanup may be needed")
            
            # Clean up any range-specific log files
            log_pattern = f"*{range_id}*.log"
            log_files = glob.glob(str(cyber_range_dir / log_pattern))
            for log_file in log_files:
                try:
                    Path(log_file).unlink()
                    self.logger.info(f"Removed log file: {Path(log_file).name}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove log file {Path(log_file).name}: {e}")
            
            # Save updated persistent data
            self._save_persistent_data()
            
            self.logger.info(f"Successfully removed range {range_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove range {range_id}: {e}")
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
    
    def create_range_from_yaml(
        self,
        description_file: Path,
        range_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Optional[str]:
        """
        Create a cyber range from a YAML description file.
        
        Args:
            description_file: Path to YAML description file
            range_id: Optional specific range ID
            dry_run: If True, validate but don't create
        
        Returns:
            Range ID if successful, None if failed
        """
        import yaml
        import random
        
        try:
            # Parse YAML description
            with open(description_file, 'r') as f:
                doc = yaml.load(f, Loader=yaml.SafeLoader)
            
            # Extract components from YAML
            hosts = []
            guests = []
            range_settings = {}
            
            for element in doc:
                if 'host_settings' in element:
                    for h in element['host_settings']:
                        host = Host(
                            h['id'], 
                            h.get('virbr_addr', '192.168.122.1'), 
                            h['mgmt_addr'], 
                            h['account']
                        )
                        hosts.append(host)
                
                if 'guest_settings' in element:
                    for g in element['guest_settings']:
                        guest = Guest(
                            guest_id=g['id'],
                            basevm_addr=g.get('ip_addr', '192.168.1.100'),
                            root_passwd=g.get('root_passwd', 'password'),
                            basevm_host=g['basevm_host'],
                            basevm_config_file=g.get('basevm_config_file', ''),
                            basevm_os_type=g.get('os_type', 'linux'),
                            basevm_type=g.get('basevm_type', 'kvm'),
                            basevm_name=g.get('basevm_name', g['id']),
                            tasks=g.get('tasks', [])
                        )
                        guests.append(guest)
                
                if 'clone_settings' in element:
                    for c in element['clone_settings']:
                        range_settings = c
            
            # Generate range ID if not provided
            if range_id is None:
                range_id = range_settings.get('range_id', random.randint(1000, 9999))
            
            range_id_str = str(range_id)
            
            if dry_run:
                self.logger.info(f"DRY RUN: Would create range {range_id_str} with {len(hosts)} hosts and {len(guests)} guests")
                return range_id_str
            
            # Create the range using existing method
            result = self.create_range(
                range_id=range_id_str,
                name=f"Range {range_id_str}",
                description=f"Range created from {description_file.name}",
                hosts=hosts,
                guests=guests,
                tags={"source_file": str(description_file)}
            )
            
            return result.range_id
            
        except Exception as e:
            self.logger.error(f"Failed to create range from YAML {description_file}: {e}")
            raise
    
    def _load_persistent_data(self) -> None:
        """Load persistent data from disk"""
        try:
            # Load range metadata
            if self._metadata_file.exists():
                with open(self._metadata_file, 'r') as f:
                    metadata_data = json.load(f)
                    for range_id, data in metadata_data.items():
                        self._ranges[range_id] = RangeMetadata.from_dict(data)
                self.logger.info(f"Loaded {len(self._ranges)} ranges from persistent storage")
            
            # Load range resources
            if self._resources_file.exists():
                with open(self._resources_file, 'r') as f:
                    self._range_resources = json.load(f)
                self.logger.info(f"Loaded resources for {len(self._range_resources)} ranges")
                
        except Exception as e:
            self.logger.error(f"Failed to load persistent data: {e}")
            # Continue with empty registry if loading fails
            self._ranges = {}
            self._range_resources = {}
    
    def _save_persistent_data(self) -> None:
        """Save persistent data to disk"""
        try:
            # Save range metadata
            metadata_data = {
                range_id: metadata.to_dict()
                for range_id, metadata in self._ranges.items()
            }
            with open(self._metadata_file, 'w') as f:
                json.dump(metadata_data, f, indent=2)
            
            # Save range resources
            with open(self._resources_file, 'w') as f:
                json.dump(self._range_resources, f, indent=2)
                
            self.logger.debug("Persistent data saved successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to save persistent data: {e}")
    
    def _create_entry_point(
        self, 
        entry_point: EntryPointInfo, 
        local_user: str, 
        host_address: str
    ) -> Dict[str, Any]:
        """
        Create entry point (internal method)
        
        Args:
            entry_point: Entry point information
            local_user: Local user
            host_address: Host address
            
        Returns:
            Dict: Access information
        """
        return self.gateway_service.create_entry_point(entry_point, local_user, host_address)
    
    def get_access_notification(self, range_id: int) -> str:
        """
        Get access notification
        
        Args:
            range_id: Range ID
            
        Returns:
            str: Access notification content
        """
        return self.gateway_service.generate_access_notification(range_id)
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status (including gateway information)
        
        Returns:
            Dict: System status information
        """
        base_status = {
            'total_ranges': len(self._ranges),
            'active_ranges': len([r for r in self._ranges.values() if r.status == RangeStatus.ACTIVE]),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add gateway service status
        try:
            gateway_status = self.gateway_service.get_service_status()
            base_status['gateway_service'] = gateway_status
        except Exception as e:
            self.logger.error(f"Failed to get gateway service status: {e}")
            base_status['gateway_service'] = {'error': str(e)}
        
        return base_status
    
    def create_cyber_range(self, yaml_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create cyber range (integrated gateway functionality)
        
        Args:
            yaml_config: YAML configuration
            
        Returns:
            Dict: Creation result
        """
        try:
            # Parse configuration to get range_id
            clone_settings = yaml_config.get('clone_settings', [{}])[0]
            range_id = clone_settings.get('range_id')
            
            if not range_id:
                raise ValueError("Missing range_id in configuration")
            
            self.logger.info(f"Creating cyber range {range_id}")
            
            # Create basic range - Call legacy CyRIS system
            range_resources = self._create_actual_cyber_range(yaml_config, range_id)
            
            # Parse entry points and create gateway tunnels
            entry_points = []
            hosts_config = clone_settings.get('hosts', [])
            
            for host_config in hosts_config:
                host_id = host_config.get('host_id')
                guests_config = host_config.get('guests', [])
                
                for instance_id in range(1, host_config.get('instance_number', 0) + 1):
                    for guest_config in guests_config:
                        if guest_config.get('entry_point'):
                            # Create entry point
                            port = self.gateway_service.get_available_port()
                            password = self.gateway_service.generate_random_credentials()
                            
                            entry_point = EntryPointInfo(
                                range_id=range_id,
                                instance_id=instance_id,
                                guest_id=guest_config.get('guest_id'),
                                port=port,
                                target_host=f"192.168.{range_id}.{100 + instance_id}",
                                target_port=22,
                                account="trainee",
                                password=password
                            )
                            
                            # 通过网关服务Create entry point
                            access_info = self._create_entry_point(entry_point, "ubuntu", "10.0.1.100")
                            entry_points.append(access_info)
            
            # Create range metadata
            metadata = RangeMetadata(
                range_id=str(range_id),
                name=f"Range {range_id}",
                description=f"Cyber range instance {range_id}",
                status=RangeStatus.ACTIVE,
                created_at=datetime.now()
            )
            
            self._ranges[str(range_id)] = metadata
            
            # Record range resources
            self._range_resources[str(range_id)] = range_resources
            
            self._save_persistent_data()
            
            result = {
                'success': True,
                'range_id': range_id,
                'entry_points': entry_points,
                'message': f"Cyber range {range_id} created successfully"
            }
            
            self.logger.info(f"Cyber range {range_id} created with {len(entry_points)} entry points")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to create cyber range: {e}")
            return {
                'success': False,
                'error': str(e),
                'range_id': range_id if 'range_id' in locals() else None
            }
    
    def destroy_cyber_range(self, range_id: int) -> Dict[str, Any]:
        """
        Destroy cyber range (including gateway cleanup)
        
        Args:
            range_id: Range ID
            
        Returns:
            Dict: Destruction result
        """
        try:
            self.logger.info(f"Destroying cyber range {range_id}")
            
            # Clean up gateway resources
            self.gateway_service.cleanup_range(range_id)
            
            # Clean up actual range resources
            range_resources = self._range_resources.get(str(range_id), {})
            self._cleanup_actual_resources(range_id, range_resources)
            
            # Clean up range metadata
            range_id_str = str(range_id)
            if range_id_str in self._ranges:
                del self._ranges[range_id_str]
            
            if range_id_str in self._range_resources:
                del self._range_resources[range_id_str]
            
            self._save_persistent_data()
            
            result = {
                'success': True,
                'range_id': range_id,
                'message': f"Cyber range {range_id} destroyed successfully"
            }
            
            self.logger.info(f"Cyber range {range_id} destroyed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to destroy cyber range {range_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'range_id': range_id
            }
    
    def _create_actual_cyber_range(self, yaml_config: Dict[str, Any], range_id: int) -> Dict[str, List[str]]:
        """
        Call legacy CyRIS system创建实际的靶场
        
        Args:
            yaml_config: YAML configuration
            range_id: Range ID
            
        Returns:
            Dict: List of created resources {'vms': [...], 'disks': [...], 'networks': [...]}
        """
        import subprocess
        import tempfile
        import yaml
        import time
        
        resources = {
            'vms': [],
            'disks': [],
            'networks': []
        }
        
        try:
            # Create temporary YAML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as tmp_file:
                yaml.dump(yaml_config, tmp_file, default_flow_style=False)
                temp_yaml_path = tmp_file.name
            
            # Call legacy CyRIS main program
            legacy_command = [
                'python3', 
                str(self.settings.cyris_path / 'main' / 'cyris.py'),
                temp_yaml_path,
                str(self.settings.cyris_path / 'CONFIG')
            ]
            
            self.logger.info(f"Executing legacy CyRIS: {' '.join(legacy_command)}")
            
            # Execute legacy command
            result = subprocess.run(
                legacy_command,
                cwd=str(self.settings.cyris_path),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"Legacy CyRIS completed successfully for range {range_id}")
                
                # Wait for VMs to fully start
                time.sleep(5)
                
                # Discover created resources
                resources = self._discover_created_resources(range_id)
                
            else:
                error_msg = f"Legacy CyRIS failed: {result.stderr}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Clean up temporary files
            import os
            try:
                os.unlink(temp_yaml_path)
            except:
                pass
                
        except Exception as e:
            self.logger.error(f"Failed to create cyber range {range_id}: {e}")
            # If creation fails, try to clean up partially created resources
            self._cleanup_partial_resources(range_id, resources)
            raise
        
        return resources
    
    def _discover_created_resources(self, range_id: int) -> Dict[str, List[str]]:
        """
        Discover newly created range resources
        
        Args:
            range_id: Range ID
            
        Returns:
            Dict: Discovered resources
        """
        resources = {
            'vms': [],
            'disks': [],
            'networks': []
        }
        
        try:
            # Discover virtual machines
            from cyris.infrastructure.providers.virsh_client import VirshLibvirt
            virsh_client = VirshLibvirt()
            
            all_vms = virsh_client.list_all_domains()
            for vm in all_vms:
                if vm['name'].startswith('cyris-'):
                    resources['vms'].append(vm['name'])
                    self.logger.debug(f"Discovered VM: {vm['name']}")
            
            # Discover disk files
            cyber_range_dir = Path(self.settings.cyber_range_dir)
            for disk_file in cyber_range_dir.glob("*.qcow2"):
                if disk_file.name.startswith('cyris-'):
                    resources['disks'].append(disk_file.name)
                    self.logger.debug(f"Discovered disk: {disk_file.name}")
            
            # 记录Discovered resources数量
            self.logger.info(f"Discovered {len(resources['vms'])} VMs, {len(resources['disks'])} disks for range {range_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to discover resources for range {range_id}: {e}")
        
        return resources
    
    def _cleanup_partial_resources(self, range_id: int, resources: Dict[str, List[str]]):
        """
        Clean up partially created resources
        
        Args:
            range_id: Range ID
            resources: Resources to clean up
        """
        self.logger.info(f"Cleaning up partial resources for range {range_id}")
        
        try:
            from cyris.infrastructure.providers.virsh_client import VirshLibvirt
            virsh_client = VirshLibvirt()
            
            # Clean up virtual machines
            for vm_name in resources.get('vms', []):
                try:
                    virsh_client.destroy_domain(vm_name)
                    virsh_client.undefine_domain(vm_name)
                    self.logger.debug(f"Cleaned up VM: {vm_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup VM {vm_name}: {e}")
            
            # Clean up disk files
            for disk_name in resources.get('disks', []):
                try:
                    disk_path = Path(self.settings.cyber_range_dir) / disk_name
                    if disk_path.exists():
                        disk_path.unlink()
                        self.logger.debug(f"Cleaned up disk: {disk_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup disk {disk_name}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error during resource cleanup: {e}")
    
    def _cleanup_actual_resources(self, range_id: int, resources: Dict[str, List[str]]):
        """
        Clean up actual range resources
        
        Args:
            range_id: Range ID
            resources: Resources to clean up
        """
        self.logger.info(f"Cleaning up actual resources for range {range_id}")
        
        try:
            # First try to use legacy cleanup script
            try:
                import subprocess
                cleanup_command = [
                    'bash',
                    str(self.settings.cyris_path / 'main' / 'range_cleanup.sh'),
                    str(range_id),
                    str(self.settings.cyris_path / 'CONFIG')
                ]
                
                result = subprocess.run(
                    cleanup_command,
                    cwd=str(self.settings.cyris_path),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    self.logger.info(f"Legacy cleanup completed for range {range_id}")
                else:
                    self.logger.warning(f"Legacy cleanup failed, fallback to manual cleanup: {result.stderr}")
                    # Continue with manual cleanup
                    
            except Exception as e:
                self.logger.warning(f"Legacy cleanup not available, using manual cleanup: {e}")
            
            # Manually clean up resources
            self._cleanup_partial_resources(range_id, resources)
            
        except Exception as e:
            self.logger.error(f"Error during actual resource cleanup: {e}")