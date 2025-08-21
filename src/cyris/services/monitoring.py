"""
Monitoring Service

This service provides monitoring capabilities for cyber range instances,
including resource usage, health checks, and performance metrics.
"""

import logging
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .orchestrator import RangeMetadata, RangeStatus


@dataclass
class HostMetrics:
    """Resource metrics for a host"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]  # bytes_sent, bytes_recv
    load_average: List[float]  # 1, 5, 15 minute averages
    
    
@dataclass
class RangeMetrics:
    """Aggregated metrics for a cyber range"""
    range_id: str
    timestamp: datetime
    total_hosts: int
    active_hosts: int
    total_guests: int
    active_guests: int
    avg_cpu_percent: float
    avg_memory_percent: float
    total_network_io: Dict[str, int]
    status: RangeStatus
    uptime_seconds: float


@dataclass
class Alert:
    """System alert"""
    alert_id: str
    range_id: str
    severity: str  # "info", "warning", "error", "critical"
    title: str
    message: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False


class MonitoringService:
    """
    Monitoring service for cyber range instances.
    
    Provides:
    - Resource monitoring (CPU, memory, disk, network)
    - Health checks
    - Performance metrics collection
    - Alerting based on thresholds
    - Historical data tracking
    
    Follows SOLID principles:
    - Single Responsibility: Focuses on monitoring and metrics
    - Open/Closed: Extensible via metric collectors and alert handlers
    - Interface Segregation: Focused monitoring interface
    - Dependency Inversion: Uses abstract interfaces for data collection
    """
    
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        metrics_retention_hours: int = 24,
        collection_interval_seconds: int = 60
    ):
        """
        Initialize monitoring service.
        
        Args:
            logger: Optional logger instance
            metrics_retention_hours: How long to keep metrics data
            collection_interval_seconds: Interval between metric collections
        """
        self.logger = logger or logging.getLogger(__name__)
        self.metrics_retention_hours = metrics_retention_hours
        self.collection_interval_seconds = collection_interval_seconds
        
        # In-memory storage (in production, would use time-series DB)
        self._range_metrics: Dict[str, List[RangeMetrics]] = {}
        self._host_metrics: Dict[str, List[HostMetrics]] = {}
        self._alerts: Dict[str, Alert] = {}
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._range_registry: Dict[str, RangeMetadata] = {}
        
        # Alert thresholds (configurable)
        self.alert_thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "host_down_threshold": 0.5  # Alert if >50% hosts are down
        }
        
        # Alert callbacks
        self._alert_handlers: List[Callable[[Alert], None]] = []
        
        self.logger.info("MonitoringService initialized")
    
    def register_range(self, range_metadata: RangeMetadata) -> None:
        """Register a range for monitoring"""
        self._range_registry[range_metadata.range_id] = range_metadata
        self._range_metrics[range_metadata.range_id] = []
        
        self.logger.info(f"Registered range {range_metadata.range_id} for monitoring")
    
    def unregister_range(self, range_id: str) -> None:
        """Unregister a range from monitoring"""
        self._range_registry.pop(range_id, None)
        self._range_metrics.pop(range_id, None)
        
        # Clean up host metrics for this range
        for host_id in list(self._host_metrics.keys()):
            if host_id.startswith(range_id):
                self._host_metrics.pop(host_id, None)
        
        self.logger.info(f"Unregistered range {range_id} from monitoring")
    
    def start_monitoring(self) -> None:
        """Start background monitoring"""
        if self._monitoring_active:
            self.logger.warning("Monitoring already active")
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="CyRIS-Monitoring"
        )
        self._monitoring_thread.start()
        
        self.logger.info("Started monitoring service")
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring"""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5.0)
        
        self.logger.info("Stopped monitoring service")
    
    def collect_range_metrics(self, range_id: str) -> Optional[RangeMetrics]:
        """
        Collect current metrics for a range.
        
        Args:
            range_id: Range identifier
        
        Returns:
            Current range metrics or None if range not found
        """
        range_metadata = self._range_registry.get(range_id)
        if not range_metadata:
            return None
        
        try:
            # In a real implementation, this would query the infrastructure
            # provider for actual resource metrics
            # For now, we'll simulate some metrics
            
            timestamp = datetime.now()
            
            # Simulate host and guest counts
            total_hosts = 2  # Would come from infrastructure provider
            active_hosts = 2 if range_metadata.status == RangeStatus.ACTIVE else 0
            total_guests = 4  # Would come from infrastructure provider  
            active_guests = 4 if range_metadata.status == RangeStatus.ACTIVE else 0
            
            # Simulate resource usage
            avg_cpu = 25.5 if range_metadata.status == RangeStatus.ACTIVE else 0.0
            avg_memory = 45.2 if range_metadata.status == RangeStatus.ACTIVE else 0.0
            
            # Calculate uptime
            uptime_seconds = (timestamp - range_metadata.created_at).total_seconds()
            
            metrics = RangeMetrics(
                range_id=range_id,
                timestamp=timestamp,
                total_hosts=total_hosts,
                active_hosts=active_hosts,
                total_guests=total_guests,
                active_guests=active_guests,
                avg_cpu_percent=avg_cpu,
                avg_memory_percent=avg_memory,
                total_network_io={"bytes_sent": 1024000, "bytes_recv": 2048000},
                status=range_metadata.status,
                uptime_seconds=uptime_seconds
            )
            
            # Store metrics
            self._range_metrics[range_id].append(metrics)
            self._cleanup_old_metrics(range_id)
            
            # Check for alerts
            self._check_range_alerts(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics for range {range_id}: {e}")
            return None
    
    def collect_host_metrics(self, host_id: str) -> Optional[HostMetrics]:
        """
        Collect current metrics for a host.
        
        Args:
            host_id: Host identifier
        
        Returns:
            Current host metrics or None if collection fails
        """
        try:
            # In a real implementation, this would connect to the host
            # and collect actual metrics via SSH or monitoring agent
            # For now, we'll use local system metrics as simulation
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            load_avg = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            
            metrics = HostMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                network_io={
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv
                },
                load_average=load_avg
            )
            
            # Store metrics
            if host_id not in self._host_metrics:
                self._host_metrics[host_id] = []
            self._host_metrics[host_id].append(metrics)
            self._cleanup_old_host_metrics(host_id)
            
            # Check for host-level alerts
            self._check_host_alerts(host_id, metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics for host {host_id}: {e}")
            return None
    
    def get_range_metrics_history(
        self, 
        range_id: str, 
        hours: int = 1
    ) -> List[RangeMetrics]:
        """Get historical metrics for a range"""
        metrics = self._range_metrics.get(range_id, [])
        cutoff = datetime.now() - timedelta(hours=hours)
        return [m for m in metrics if m.timestamp >= cutoff]
    
    def get_host_metrics_history(
        self, 
        host_id: str, 
        hours: int = 1
    ) -> List[HostMetrics]:
        """Get historical metrics for a host"""
        metrics = self._host_metrics.get(host_id, [])
        cutoff = datetime.now() - timedelta(hours=hours)
        return [m for m in metrics if m.timestamp >= cutoff]
    
    def get_active_alerts(
        self, 
        range_id: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """Get active (unresolved) alerts with optional filtering"""
        alerts = [a for a in self._alerts.values() if not a.resolved]
        
        if range_id:
            alerts = [a for a in alerts if a.range_id == range_id]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an alert"""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.acknowledged = True
            self.logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Resolve an alert"""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.resolved = True
            self.logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return True
        return False
    
    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler callback"""
        self._alert_handlers.append(handler)
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """Get monitoring service statistics"""
        total_metrics = sum(len(metrics) for metrics in self._range_metrics.values())
        total_host_metrics = sum(len(metrics) for metrics in self._host_metrics.values())
        active_alerts = len(self.get_active_alerts())
        
        return {
            "monitored_ranges": len(self._range_registry),
            "total_range_metrics": total_metrics,
            "total_host_metrics": total_host_metrics,
            "active_alerts": active_alerts,
            "monitoring_active": self._monitoring_active,
            "collection_interval": self.collection_interval_seconds,
            "metrics_retention_hours": self.metrics_retention_hours
        }
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop (runs in background thread)"""
        self.logger.info("Monitoring loop started")
        
        while self._monitoring_active:
            try:
                # Collect metrics for all registered ranges
                for range_id in list(self._range_registry.keys()):
                    if not self._monitoring_active:
                        break
                    self.collect_range_metrics(range_id)
                
                # Sleep until next collection
                time.sleep(self.collection_interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.collection_interval_seconds)
        
        self.logger.info("Monitoring loop stopped")
    
    def _check_range_alerts(self, metrics: RangeMetrics) -> None:
        """Check for range-level alert conditions"""
        # CPU threshold alert
        if metrics.avg_cpu_percent > self.alert_thresholds["cpu_percent"]:
            self._create_alert(
                range_id=metrics.range_id,
                severity="warning",
                title="High CPU Usage",
                message=f"Average CPU usage ({metrics.avg_cpu_percent:.1f}%) exceeds threshold ({self.alert_thresholds['cpu_percent']}%)"
            )
        
        # Memory threshold alert
        if metrics.avg_memory_percent > self.alert_thresholds["memory_percent"]:
            self._create_alert(
                range_id=metrics.range_id,
                severity="warning", 
                title="High Memory Usage",
                message=f"Average memory usage ({metrics.avg_memory_percent:.1f}%) exceeds threshold ({self.alert_thresholds['memory_percent']}%)"
            )
        
        # Host availability alert
        if metrics.total_hosts > 0:
            availability = metrics.active_hosts / metrics.total_hosts
            if availability < (1.0 - self.alert_thresholds["host_down_threshold"]):
                self._create_alert(
                    range_id=metrics.range_id,
                    severity="error",
                    title="Host Availability Issue",
                    message=f"Only {metrics.active_hosts}/{metrics.total_hosts} hosts are active"
                )
    
    def _check_host_alerts(self, host_id: str, metrics: HostMetrics) -> None:
        """Check for host-level alert conditions"""
        range_id = host_id.split('-')[0]  # Assuming host_id format: range_id-host_name
        
        # Disk space alert
        if metrics.disk_percent > self.alert_thresholds["disk_percent"]:
            self._create_alert(
                range_id=range_id,
                severity="error",
                title="Low Disk Space",
                message=f"Host {host_id} disk usage ({metrics.disk_percent:.1f}%) exceeds threshold ({self.alert_thresholds['disk_percent']}%)"
            )
    
    def _create_alert(
        self,
        range_id: str,
        severity: str,
        title: str,
        message: str
    ) -> None:
        """Create a new alert"""
        alert_id = f"{range_id}-{int(time.time())}-{hash(title) % 1000}"
        
        # Check if similar alert already exists and is active
        existing_alerts = [
            a for a in self._alerts.values() 
            if a.range_id == range_id and a.title == title and not a.resolved
        ]
        
        if existing_alerts:
            return  # Don't create duplicate alerts
        
        alert = Alert(
            alert_id=alert_id,
            range_id=range_id,
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.now()
        )
        
        self._alerts[alert_id] = alert
        
        # Call alert handlers
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")
        
        self.logger.warning(f"Alert created: {title} - {message}")
    
    def _cleanup_old_metrics(self, range_id: str) -> None:
        """Clean up old range metrics"""
        cutoff = datetime.now() - timedelta(hours=self.metrics_retention_hours)
        metrics = self._range_metrics.get(range_id, [])
        self._range_metrics[range_id] = [m for m in metrics if m.timestamp >= cutoff]
    
    def _cleanup_old_host_metrics(self, host_id: str) -> None:
        """Clean up old host metrics"""
        cutoff = datetime.now() - timedelta(hours=self.metrics_retention_hours)
        metrics = self._host_metrics.get(host_id, [])
        self._host_metrics[host_id] = [m for m in metrics if m.timestamp >= cutoff]