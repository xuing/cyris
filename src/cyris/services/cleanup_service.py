"""
Cleanup Service

This service handles the cleanup and destruction of cyber range resources,
ensuring proper resource deallocation and data archival.
"""

# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import logging  # Keep for type annotations
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum
import json
import tarfile
import tempfile

from .orchestrator import RangeMetadata, RangeStatus, InfrastructureProvider


class CleanupPolicy(Enum):
    """Cleanup policy options"""
    IMMEDIATE = "immediate"  # Cleanup immediately
    SCHEDULED = "scheduled"  # Cleanup at scheduled time
    ARCHIVE_THEN_CLEANUP = "archive_then_cleanup"  # Archive data first
    MANUAL = "manual"  # Manual cleanup only


@dataclass
class CleanupTask:
    """Represents a cleanup task"""
    task_id: str
    range_id: str
    range_name: str
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    policy: CleanupPolicy = CleanupPolicy.IMMEDIATE
    archive_logs: bool = True
    archive_configs: bool = True
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed
    error_message: Optional[str] = None


class CleanupService:
    """
    Service for cleaning up cyber range resources and data.
    
    Responsibilities:
    - Resource cleanup (VMs, networks, storage)
    - Data archival (logs, configurations, metrics)
    - Scheduled cleanup tasks
    - Cleanup policy enforcement
    - Resource usage reporting
    
    Follows SOLID principles:
    - Single Responsibility: Focuses on cleanup and resource management
    - Open/Closed: Extensible cleanup policies and archivers
    - Liskov Substitution: Works with any infrastructure provider
    - Interface Segregation: Focused cleanup interface
    - Dependency Inversion: Depends on provider abstractions
    """
    
    def __init__(
        self,
        infrastructure_provider: InfrastructureProvider,
        cyber_range_dir: Path,
        archive_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize cleanup service.
        
        Args:
            infrastructure_provider: Provider for infrastructure operations
            cyber_range_dir: Directory containing range data
            archive_dir: Directory for archived data (optional)
            logger: Optional logger instance
        """
        self.provider = infrastructure_provider
        self.cyber_range_dir = Path(cyber_range_dir)
        self.archive_dir = Path(archive_dir) if archive_dir else self.cyber_range_dir / "archive"
        self.logger = logger or get_logger(__name__, "cleanup_service")
        
        # Ensure directories exist
        self.cyber_range_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        
        # Cleanup tasks tracking
        self._cleanup_tasks: Dict[str, CleanupTask] = {}
        
        # Default cleanup policies
        self.default_policies = {
            "test_ranges": CleanupPolicy.IMMEDIATE,
            "training_ranges": CleanupPolicy.ARCHIVE_THEN_CLEANUP,
            "production_ranges": CleanupPolicy.MANUAL
        }
        
        # Archive settings
        self.archive_settings = {
            "compression": "gzip",  # gzip, bz2, xz
            "max_archive_age_days": 90,  # Auto-delete archives older than this
            "include_vm_snapshots": False,  # Include VM disk snapshots in archive
            "include_network_configs": True,  # Include network configurations
        }
        
        self.logger.info("CleanupService initialized")
    
    def schedule_cleanup(
        self,
        range_metadata: RangeMetadata,
        policy: Optional[CleanupPolicy] = None,
        scheduled_at: Optional[datetime] = None,
        archive_logs: bool = True,
        archive_configs: bool = True
    ) -> str:
        """
        Schedule a cleanup task for a range.
        
        Args:
            range_metadata: Range metadata
            policy: Cleanup policy to use
            scheduled_at: When to execute cleanup (None for immediate)
            archive_logs: Whether to archive log files
            archive_configs: Whether to archive configuration files
        
        Returns:
            Task ID for the scheduled cleanup
        """
        # Determine policy if not specified
        if policy is None:
            policy = self._determine_cleanup_policy(range_metadata)
        
        # Create cleanup task
        task_id = f"cleanup-{range_metadata.range_id}-{int(datetime.now().timestamp())}"
        
        cleanup_task = CleanupTask(
            task_id=task_id,
            range_id=range_metadata.range_id,
            range_name=range_metadata.name,
            created_at=datetime.now(),
            scheduled_at=scheduled_at,
            policy=policy,
            archive_logs=archive_logs,
            archive_configs=archive_configs
        )
        
        self._cleanup_tasks[task_id] = cleanup_task
        
        # If immediate cleanup, execute now
        if policy == CleanupPolicy.IMMEDIATE or scheduled_at is None:
            self._execute_cleanup_task(task_id, range_metadata)
        
        self.logger.info(
            f"Scheduled cleanup task {task_id} for range {range_metadata.range_id} "
            f"with policy {policy.value}"
        )
        
        return task_id
    
    def execute_immediate_cleanup(
        self,
        range_metadata: RangeMetadata,
        resource_ids: Dict[str, List[str]],
        archive_data: bool = True
    ) -> bool:
        """
        Execute immediate cleanup of a range.
        
        Args:
            range_metadata: Range metadata
            resource_ids: Infrastructure resource IDs to cleanup
            archive_data: Whether to archive data before cleanup
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Starting immediate cleanup for range {range_metadata.range_id}")
        
        try:
            # Archive data if requested
            if archive_data:
                archive_path = self._archive_range_data(range_metadata)
                self.logger.info(f"Range data archived to {archive_path}")
            
            # Cleanup infrastructure resources
            self._cleanup_infrastructure(range_metadata.range_id, resource_ids)
            
            # Cleanup local data
            self._cleanup_local_data(range_metadata.range_id)
            
            self.logger.info(f"Successfully completed immediate cleanup for range {range_metadata.range_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Immediate cleanup failed for range {range_metadata.range_id}: {e}")
            return False
    
    def get_cleanup_task(self, task_id: str) -> Optional[CleanupTask]:
        """Get cleanup task by ID"""
        return self._cleanup_tasks.get(task_id)
    
    def list_cleanup_tasks(
        self,
        range_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[CleanupTask]:
        """List cleanup tasks with optional filtering"""
        tasks = list(self._cleanup_tasks.values())
        
        if range_id:
            tasks = [t for t in tasks if t.range_id == range_id]
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def get_archive_info(self, range_id: str) -> Optional[Dict[str, Any]]:
        """
        Get archive information for a range.
        
        Args:
            range_id: Range identifier
        
        Returns:
            Archive information or None if not found
        """
        archive_pattern = f"{range_id}_*.tar.gz"
        archive_files = list(self.archive_dir.glob(archive_pattern))
        
        if not archive_files:
            return None
        
        # Get the most recent archive
        latest_archive = max(archive_files, key=lambda f: f.stat().st_mtime)
        
        return {
            "range_id": range_id,
            "archive_path": str(latest_archive),
            "archive_size_mb": latest_archive.stat().st_size / (1024 * 1024),
            "created_at": datetime.fromtimestamp(latest_archive.stat().st_ctime),
            "modified_at": datetime.fromtimestamp(latest_archive.stat().st_mtime),
        }
    
    def restore_from_archive(
        self,
        range_id: str,
        target_dir: Optional[Path] = None
    ) -> bool:
        """
        Restore range data from archive.
        
        Args:
            range_id: Range identifier
            target_dir: Target directory for restoration (default: cyber_range_dir)
        
        Returns:
            True if successful, False otherwise
        """
        archive_info = self.get_archive_info(range_id)
        if not archive_info:
            self.logger.error(f"No archive found for range {range_id}")
            return False
        
        target_path = target_dir or self.cyber_range_dir
        archive_path = Path(archive_info["archive_path"])
        
        try:
            self.logger.info(f"Restoring range {range_id} from archive {archive_path}")
            
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(target_path)
            
            self.logger.info(f"Successfully restored range {range_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore range {range_id}: {e}")
            return False
    
    def cleanup_old_archives(self, max_age_days: Optional[int] = None) -> int:
        """
        Clean up old archives based on age.
        
        Args:
            max_age_days: Maximum age in days (uses default if None)
        
        Returns:
            Number of archives cleaned up
        """
        max_age = max_age_days or self.archive_settings["max_archive_age_days"]
        cutoff_time = datetime.now() - timedelta(days=max_age)
        
        cleaned_count = 0
        
        for archive_file in self.archive_dir.glob("*.tar.*"):
            if datetime.fromtimestamp(archive_file.stat().st_mtime) < cutoff_time:
                try:
                    archive_file.unlink()
                    cleaned_count += 1
                    self.logger.info(f"Cleaned up old archive: {archive_file.name}")
                except Exception as e:
                    self.logger.error(f"Failed to cleanup archive {archive_file}: {e}")
        
        self.logger.info(f"Cleaned up {cleaned_count} old archives")
        return cleaned_count
    
    def get_disk_usage_stats(self) -> Dict[str, Any]:
        """Get disk usage statistics for range and archive directories"""
        def get_dir_size(path: Path) -> int:
            """Get total size of directory in bytes"""
            total = 0
            try:
                for item in path.rglob('*'):
                    if item.is_file():
                        total += item.stat().st_size
            except (OSError, PermissionError):
                pass
            return total
        
        range_dir_size = get_dir_size(self.cyber_range_dir)
        archive_dir_size = get_dir_size(self.archive_dir)
        
        return {
            "cyber_range_dir_mb": range_dir_size / (1024 * 1024),
            "archive_dir_mb": archive_dir_size / (1024 * 1024),
            "total_usage_mb": (range_dir_size + archive_dir_size) / (1024 * 1024),
            "archive_count": len(list(self.archive_dir.glob("*.tar.*"))),
            "range_count": len([d for d in self.cyber_range_dir.iterdir() if d.is_dir()])
        }
    
    def _determine_cleanup_policy(self, range_metadata: RangeMetadata) -> CleanupPolicy:
        """Determine cleanup policy based on range metadata"""
        # Check tags for explicit policy
        if "cleanup_policy" in range_metadata.tags:
            try:
                return CleanupPolicy(range_metadata.tags["cleanup_policy"])
            except ValueError:
                pass
        
        # Determine by range type or name
        range_name_lower = range_metadata.name.lower()
        
        if "test" in range_name_lower or "demo" in range_name_lower:
            return CleanupPolicy.IMMEDIATE
        elif "training" in range_name_lower or "workshop" in range_name_lower:
            return CleanupPolicy.ARCHIVE_THEN_CLEANUP
        else:
            return CleanupPolicy.MANUAL
    
    def _execute_cleanup_task(self, task_id: str, range_metadata: RangeMetadata) -> None:
        """Execute a cleanup task"""
        task = self._cleanup_tasks.get(task_id)
        if not task:
            return
        
        self.logger.info(f"Executing cleanup task {task_id}")
        task.status = "running"
        
        try:
            # Archive data if required by policy
            if task.policy == CleanupPolicy.ARCHIVE_THEN_CLEANUP:
                self._archive_range_data(range_metadata)
            
            # Cleanup infrastructure (would need resource IDs from orchestrator)
            # For now, we'll just cleanup local data
            self._cleanup_local_data(task.range_id)
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
            self.logger.info(f"Cleanup task {task_id} completed successfully")
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self.logger.error(f"Cleanup task {task_id} failed: {e}")
    
    def _archive_range_data(self, range_metadata: RangeMetadata) -> Path:
        """Archive range data to compressed file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{range_metadata.range_id}_{timestamp}.tar.gz"
        archive_path = self.archive_dir / archive_name
        
        range_dir = self.cyber_range_dir / range_metadata.range_id
        
        if not range_dir.exists():
            self.logger.warning(f"Range directory not found: {range_dir}")
            return archive_path
        
        self.logger.info(f"Creating archive for range {range_metadata.range_id}")
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            # Add range metadata
            metadata_str = json.dumps({
                "range_id": range_metadata.range_id,
                "name": range_metadata.name,
                "description": range_metadata.description,
                "created_at": range_metadata.created_at.isoformat(),
                "archived_at": datetime.now().isoformat(),
                "owner": range_metadata.owner,
                "tags": range_metadata.tags
            }, indent=2)
            
            metadata_info = tarfile.TarInfo(name="metadata.json")
            metadata_info.size = len(metadata_str.encode())
            tar.addfile(metadata_info, fileobj=tempfile.BytesIO(metadata_str.encode()))
            
            # Add range directory contents
            tar.add(range_dir, arcname=range_metadata.range_id)
        
        self.logger.info(f"Archive created: {archive_path} ({archive_path.stat().st_size / (1024*1024):.1f} MB)")
        return archive_path
    
    def _cleanup_infrastructure(self, range_id: str, resource_ids: Dict[str, List[str]]) -> None:
        """Cleanup infrastructure resources"""
        self.logger.info(f"Cleaning up infrastructure for range {range_id}")
        
        # Destroy guests first
        guest_ids = resource_ids.get("guests", [])
        if guest_ids:
            self.provider.destroy_guests(guest_ids)
            self.logger.info(f"Destroyed {len(guest_ids)} guests")
        
        # Then destroy hosts
        host_ids = resource_ids.get("hosts", [])
        if host_ids:
            self.provider.destroy_hosts(host_ids)
            self.logger.info(f"Destroyed {len(host_ids)} hosts")
    
    def _cleanup_local_data(self, range_id: str) -> None:
        """Cleanup local range data directory"""
        range_dir = self.cyber_range_dir / range_id
        
        if range_dir.exists():
            self.logger.info(f"Removing local data for range {range_id}")
            shutil.rmtree(range_dir)
        else:
            self.logger.warning(f"Range directory not found: {range_dir}")