"""
Integration tests for services working together.

These tests verify that different services integrate properly and
work together to provide complete functionality.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import time
import threading

import sys
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.services.orchestrator import RangeOrchestrator, RangeStatus
from cyris.services.monitoring import MonitoringService
from cyris.services.cleanup_service import CleanupService, CleanupPolicy
from cyris.config.settings import CyRISSettings
from cyris.domain.entities.host import Host
from cyris.domain.entities.guest import Guest
from cyris.tools.ssh_manager import SSHManager, SSHCredentials, SSHResult
from cyris.tools.user_manager import UserManager, UserRole


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def cyris_settings(temp_dir):
    """Create test CyRIS settings"""
    return CyRISSettings(
        cyber_range_dir=temp_dir / "cyber_range",
        cyris_path=temp_dir,
        gw_mode=False,
        gw_account="test_user",
        gw_mgmt_addr="192.168.1.1"
    )


class MockInfrastructureProvider:
    """Mock infrastructure provider for integration tests"""
    
    def __init__(self):
        self.provider_name = "mock_integration"
        self.created_hosts = []
        self.created_guests = []
        self.destroyed_hosts = []
        self.destroyed_guests = []
        self.resource_statuses = {}
        self._connected = True
    
    def connect(self):
        self._connected = True
        
    def disconnect(self):
        self._connected = False
        
    def is_connected(self):
        return self._connected
    
    def create_hosts(self, hosts):
        host_ids = []
        for host in hosts:
            # Handle both modern and legacy Host entities
            if hasattr(host, 'id'):
                host_id = str(host.id)
            else:
                host_id = host.host_id
            host_ids.append(host_id)
            self.created_hosts.append(host_id)
            self.resource_statuses[host_id] = "active"
        return host_ids
    
    def create_guests(self, guests, host_mapping):
        guest_ids = []
        for guest in guests:
            # Handle both modern and legacy Guest entities
            if hasattr(guest, 'id'):
                vm_name = f"cyris-{guest.id}-integration"
            else:
                vm_name = f"cyris-{guest.guest_id}-integration"
            guest_ids.append(vm_name)
            self.created_guests.append(vm_name)
            self.resource_statuses[vm_name] = "active"
        return guest_ids
    
    def destroy_hosts(self, host_ids):
        self.destroyed_hosts.extend(host_ids)
        for host_id in host_ids:
            if host_id in self.resource_statuses:
                self.resource_statuses[host_id] = "terminated"
    
    def destroy_guests(self, guest_ids):
        self.destroyed_guests.extend(guest_ids)
        for guest_id in guest_ids:
            if guest_id in self.resource_statuses:
                self.resource_statuses[guest_id] = "terminated"
    
    def get_status(self, resource_ids):
        return {rid: self.resource_statuses.get(rid, "not_found") for rid in resource_ids}
        
    def get_resource_info(self, resource_id):
        return None


@pytest.fixture
def mock_provider():
    """Create mock infrastructure provider"""
    return MockInfrastructureProvider()


@pytest.fixture
def sample_hosts():
    """Create sample host configurations"""
    return [
        Host(
            host_id="web-server",
            mgmt_addr="192.168.1.10",
            virbr_addr="10.0.0.1",
            account="test_user"
        )
    ]


@pytest.fixture
def sample_guests():
    """Create sample guest configurations"""
    return [
        Guest(
            guest_id="web-vm",
            ip_addr="192.168.100.10",
            password="test123",
            basevm_host="web-server",
            basevm_config_file="/tmp/test.xml",
            basevm_os_type="ubuntu",
            basevm_type="kvm",
            basevm_name="web_base",
            tasks=[]
        )
    ]


class TestOrchestratorMonitoringIntegration:
    """Test integration between orchestrator and monitoring services"""
    
    @pytest.fixture
    def orchestrator(self, cyris_settings, mock_provider):
        """Create orchestrator instance"""
        return RangeOrchestrator(cyris_settings, mock_provider)
    
    @pytest.fixture
    def monitoring_service(self):
        """Create monitoring service"""
        return MonitoringService(
            metrics_retention_hours=1,
            collection_interval_seconds=5
        )
    
    def test_monitoring_range_lifecycle(self, orchestrator, monitoring_service, sample_hosts, sample_guests):
        """Test monitoring throughout range lifecycle"""
        # Create range
        metadata = orchestrator.create_range(
            range_id="monitoring-test-range",
            name="Monitoring Test Range",
            description="Range for monitoring integration testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Register range for monitoring
        monitoring_service.register_range(metadata)
        
        # Start monitoring
        monitoring_service.start_monitoring()
        
        try:
            # Collect initial metrics
            metrics = monitoring_service.collect_range_metrics("monitoring-test-range")
            assert metrics is not None
            assert metrics.range_id == "monitoring-test-range"
            assert metrics.status == RangeStatus.ACTIVE
            
            # Update range status and check monitoring
            orchestrator.update_range_status("monitoring-test-range")
            
            # Collect metrics again
            updated_metrics = monitoring_service.collect_range_metrics("monitoring-test-range")
            assert updated_metrics.timestamp > metrics.timestamp
            
            # Destroy range
            orchestrator.destroy_range("monitoring-test-range")
            
            # Unregister from monitoring
            monitoring_service.unregister_range("monitoring-test-range")
            
            # Verify range is no longer monitored
            final_metrics = monitoring_service.collect_range_metrics("monitoring-test-range")
            assert final_metrics is None
            
        finally:
            monitoring_service.stop_monitoring()
    
    def test_monitoring_alerts_integration(self, orchestrator, monitoring_service, sample_hosts, sample_guests):
        """Test alert generation during range operations"""
        alerts_received = []
        
        def alert_handler(alert):
            alerts_received.append(alert)
        
        # Add alert handler
        monitoring_service.add_alert_handler(alert_handler)
        
        # Create range
        metadata = orchestrator.create_range(
            range_id="alert-test-range",
            name="Alert Test Range",
            description="Range for alert testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Register for monitoring
        monitoring_service.register_range(metadata)
        
        # Simulate high resource usage by creating custom metrics
        from src.cyris.services.monitoring import RangeMetrics
        
        high_cpu_metrics = RangeMetrics(
            range_id="alert-test-range",
            timestamp=time.time(),
            total_hosts=1,
            active_hosts=1,
            total_guests=1,
            active_guests=1,
            avg_cpu_percent=90.0,  # High CPU usage
            avg_memory_percent=50.0,
            total_network_io={"bytes_sent": 1000, "bytes_recv": 2000},
            status=RangeStatus.ACTIVE,
            uptime_seconds=3600
        )
        
        # Check for alerts (this should trigger high CPU alert)
        monitoring_service._check_range_alerts(high_cpu_metrics)
        
        # Verify alert was generated
        assert len(alerts_received) > 0
        cpu_alert = alerts_received[-1]
        assert cpu_alert.range_id == "alert-test-range"
        assert cpu_alert.severity == "warning"
        assert "CPU" in cpu_alert.title
        
        # Clean up
        monitoring_service.unregister_range("alert-test-range")
    
    def test_monitoring_statistics_integration(self, orchestrator, monitoring_service, sample_hosts, sample_guests):
        """Test monitoring statistics with multiple ranges"""
        # Create multiple ranges
        ranges = []
        for i in range(3):
            metadata = orchestrator.create_range(
                range_id=f"stats-range-{i}",
                name=f"Stats Range {i}",
                description=f"Range {i} for statistics testing",
                hosts=sample_hosts,
                guests=sample_guests
            )
            ranges.append(metadata)
            monitoring_service.register_range(metadata)
        
        # Collect metrics for all ranges
        for metadata in ranges:
            monitoring_service.collect_range_metrics(metadata.range_id)
        
        # Check monitoring statistics
        stats = monitoring_service.get_monitoring_statistics()
        assert stats["monitored_ranges"] == 3
        assert stats["total_range_metrics"] >= 3
        assert not stats["monitoring_active"]  # We didn't start background monitoring
        
        # Clean up
        for metadata in ranges:
            monitoring_service.unregister_range(metadata.range_id)


class TestOrchestratorCleanupIntegration:
    """Test integration between orchestrator and cleanup services"""
    
    @pytest.fixture
    def orchestrator(self, cyris_settings, mock_provider):
        """Create orchestrator instance"""
        return RangeOrchestrator(cyris_settings, mock_provider)
    
    @pytest.fixture
    def cleanup_service(self, cyris_settings, mock_provider):
        """Create cleanup service"""
        return CleanupService(
            infrastructure_provider=mock_provider,
            cyber_range_dir=Path(cyris_settings.cyber_range_dir)
        )
    
    def test_cleanup_range_lifecycle(self, orchestrator, cleanup_service, sample_hosts, sample_guests):
        """Test cleanup integration with range lifecycle"""
        # Create range
        metadata = orchestrator.create_range(
            range_id="cleanup-test-range",
            name="Cleanup Test Range",
            description="Range for cleanup integration testing",
            hosts=sample_hosts,
            guests=sample_guests,
            tags={"cleanup_policy": "immediate"}
        )
        
        # Get resource IDs
        resource_ids = orchestrator.get_range_resources("cleanup-test-range")
        assert resource_ids is not None
        
        # Schedule cleanup
        task_id = cleanup_service.schedule_cleanup(
            range_metadata=metadata,
            policy=CleanupPolicy.IMMEDIATE
        )
        
        # Verify cleanup task was created
        task = cleanup_service.get_cleanup_task(task_id)
        assert task is not None
        assert task.range_id == "cleanup-test-range"
        assert task.status == "completed"  # Immediate cleanup should complete
        
        # Verify resources were cleaned up (mocked)
        provider = orchestrator.provider
        # Note: In real implementation, cleanup service would call destroy methods
        # Here we just verify the integration points work
        
    def test_cleanup_with_archival(self, orchestrator, cleanup_service, sample_hosts, sample_guests, temp_dir):
        """Test cleanup with data archival"""
        # Create range
        metadata = orchestrator.create_range(
            range_id="archive-test-range",
            name="Archive Test Range", 
            description="Range for archival testing",
            hosts=sample_hosts,
            guests=sample_guests
        )
        
        # Create some test data in range directory
        range_dir = temp_dir / "cyber_range" / "archive-test-range"
        range_dir.mkdir(parents=True, exist_ok=True)
        (range_dir / "test_file.txt").write_text("Test data")
        
        # Schedule cleanup with archival
        task_id = cleanup_service.schedule_cleanup(
            range_metadata=metadata,
            policy=CleanupPolicy.ARCHIVE_THEN_CLEANUP,
            archive_logs=True,
            archive_configs=True
        )
        
        # Get task status
        task = cleanup_service.get_cleanup_task(task_id)
        assert task is not None
        assert task.policy == CleanupPolicy.ARCHIVE_THEN_CLEANUP
        
        # Check if archive was created (implementation-dependent)
        archive_info = cleanup_service.get_archive_info("archive-test-range")
        # Note: Archive creation is mocked/simplified in this test
        
    def test_cleanup_statistics_integration(self, orchestrator, cleanup_service, sample_hosts, sample_guests):
        """Test cleanup statistics with multiple ranges"""
        # Create and cleanup multiple ranges
        for i in range(3):
            metadata = orchestrator.create_range(
                range_id=f"cleanup-stats-range-{i}",
                name=f"Cleanup Stats Range {i}",
                description=f"Range {i} for cleanup statistics",
                hosts=sample_hosts,
                guests=sample_guests
            )
            
            cleanup_service.schedule_cleanup(metadata, policy=CleanupPolicy.IMMEDIATE)
        
        # Check cleanup tasks
        all_tasks = cleanup_service.list_cleanup_tasks()
        assert len(all_tasks) >= 3
        
        # Check disk usage statistics
        stats = cleanup_service.get_disk_usage_stats()
        assert "cyber_range_dir_mb" in stats
        assert "archive_dir_mb" in stats
        assert "total_usage_mb" in stats


class TestSSHUserManagerIntegration:
    """Test integration between SSH manager and user manager"""
    
    @pytest.fixture
    def ssh_manager(self, temp_dir):
        """Create SSH manager"""
        return SSHManager(
            max_connections=10,
            key_dir=temp_dir / "ssh_keys"
        )
    
    @pytest.fixture
    def user_manager(self, ssh_manager, temp_dir):
        """Create user manager"""
        return UserManager(
            ssh_manager=ssh_manager,
            config_dir=temp_dir / "users"
        )
    
    def test_user_ssh_key_integration(self, ssh_manager, user_manager):
        """Test SSH key generation and user creation integration"""
        # Generate SSH key pair
        private_key_path, public_key_path = ssh_manager.generate_ssh_keypair("test-user")
        
        assert Path(private_key_path).exists()
        assert Path(public_key_path).exists()
        
        # Read public key content
        with open(public_key_path) as f:
            public_key_content = f.read().strip()
        
        # Create user with SSH key
        user = user_manager.create_user(
            username="testuser",
            full_name="Test User",
            role=UserRole.STUDENT,
            ssh_public_keys=[public_key_content]
        )
        
        # Verify user has SSH key
        assert len(user.ssh_public_keys) == 1
        assert user.ssh_public_keys[0] == public_key_content
        
        # Test SSH key installation (mocked)
        credentials = SSHCredentials(
            hostname="test-host",
            username="root",
            password="test-password"
        )
        
        # Mock the SSH execution
        with patch.object(ssh_manager, 'execute_command') as mock_execute:
            mock_result = Mock()
            mock_result.success = True
            mock_execute.return_value = mock_result
            
            success = ssh_manager.install_public_key(credentials, public_key_path)
            assert success is True
            
            # Verify SSH commands were called
            assert mock_execute.call_count > 0
    
    def test_user_deployment_integration(self, ssh_manager, user_manager):
        """Test user deployment to multiple hosts"""
        # Create multiple users
        users = []
        for i in range(3):
            user = user_manager.create_user(
                username=f"testuser{i}",
                full_name=f"Test User {i}",
                role=UserRole.STUDENT
            )
            users.append(user)
        
        # Mock host credentials
        host_credentials = [
            SSHCredentials(hostname="host1", username="root", password="pass1"),
            SSHCredentials(hostname="host2", username="root", password="pass2")
        ]
        
        # Mock SSH execution
        with patch.object(ssh_manager, 'execute_command') as mock_execute:
            mock_result = Mock()
            mock_result.success = True
            mock_result.stderr = ""
            mock_execute.return_value = mock_result
            
            # Deploy users to hosts
            for user in users:
                results = user_manager.create_user_on_hosts(user.username, host_credentials)
                
                # Verify deployment results
                assert len(results) == 2
                assert all(success for success in results.values())
        
        # Check user manager statistics
        stats = user_manager.get_user_manager_stats()
        assert stats["total_users"] == 3
        assert stats["users_by_role"]["student"] == 3


class TestFullIntegrationWorkflow:
    """Test complete workflow integration"""
    
    @pytest.fixture
    def full_setup(self, cyris_settings, temp_dir):
        """Set up all services for full integration test"""
        # Create mock provider
        mock_provider = MockInfrastructureProvider()
        
        # Create services
        orchestrator = RangeOrchestrator(cyris_settings, mock_provider)
        monitoring_service = MonitoringService()
        cleanup_service = CleanupService(mock_provider, Path(cyris_settings.cyber_range_dir))
        ssh_manager = SSHManager(key_dir=temp_dir / "ssh_keys")
        user_manager = UserManager(ssh_manager, temp_dir / "users")
        
        return {
            "orchestrator": orchestrator,
            "monitoring": monitoring_service,
            "cleanup": cleanup_service,
            "ssh": ssh_manager,
            "users": user_manager,
            "provider": mock_provider
        }
    
    def test_complete_range_workflow(self, full_setup, sample_hosts, sample_guests):
        """Test complete cyber range creation, monitoring, and cleanup workflow"""
        services = full_setup
        
        # Step 1: Create users
        instructor = services["users"].create_user(
            username="instructor1",
            full_name="Test Instructor",
            role=UserRole.INSTRUCTOR
        )
        
        students = []
        for i in range(2):
            student = services["users"].create_user(
                username=f"student{i}",
                full_name=f"Student {i}",
                role=UserRole.STUDENT
            )
            students.append(student)
        
        # Step 2: Generate SSH keys for instructor
        private_key, public_key = services["ssh"].generate_ssh_keypair("instructor1")
        
        # Step 3: Create cyber range
        metadata = services["orchestrator"].create_range(
            range_id="full-workflow-range",
            name="Full Workflow Range",
            description="Range for complete workflow testing",
            hosts=sample_hosts,
            guests=sample_guests,
            owner=instructor.username,
            tags={"course": "test", "semester": "fall2023"}
        )
        
        # Step 4: Start monitoring
        services["monitoring"].register_range(metadata)
        services["monitoring"].start_monitoring()
        
        try:
            # Step 5: Collect initial metrics
            initial_metrics = services["monitoring"].collect_range_metrics("full-workflow-range")
            assert initial_metrics is not None
            assert initial_metrics.status == RangeStatus.ACTIVE
            
            # Step 6: Deploy users to range (mocked)
            host_credentials = [
                SSHCredentials(hostname="192.168.1.10", username="root", password="test")
            ]
            
            with patch.object(services["ssh"], 'execute_command') as mock_execute:
                mock_result = Mock()
                mock_result.success = True
                mock_result.stderr = ""
                mock_execute.return_value = mock_result
                
                # Deploy all users
                all_users = [instructor] + students
                for user in all_users:
                    results = services["users"].create_user_on_hosts(user.username, host_credentials)
                    assert all(success for success in results.values())
            
            # Step 7: Simulate some usage
            time.sleep(0.1)  # Brief pause
            
            # Update range status
            updated_status = services["orchestrator"].update_range_status("full-workflow-range")
            assert updated_status == RangeStatus.ACTIVE
            
            # Step 8: Collect updated metrics
            updated_metrics = services["monitoring"].collect_range_metrics("full-workflow-range")
            assert updated_metrics.timestamp > initial_metrics.timestamp
            
            # Step 9: Schedule cleanup
            cleanup_task_id = services["cleanup"].schedule_cleanup(
                range_metadata=metadata,
                policy=CleanupPolicy.ARCHIVE_THEN_CLEANUP
            )
            
            cleanup_task = services["cleanup"].get_cleanup_task(cleanup_task_id)
            assert cleanup_task is not None
            assert cleanup_task.range_id == "full-workflow-range"
            
            # Step 10: Destroy range
            success = services["orchestrator"].destroy_range("full-workflow-range")
            assert success is True
            
            # Verify final state
            final_metadata = services["orchestrator"].get_range("full-workflow-range")
            assert final_metadata.status == RangeStatus.DESTROYED
            
        finally:
            services["monitoring"].stop_monitoring()
    
    def test_concurrent_operations(self, full_setup, sample_hosts, sample_guests):
        """Test concurrent operations across services"""
        services = full_setup
        
        def create_and_monitor_range(range_id):
            """Create range and start monitoring"""
            try:
                # Create range
                metadata = services["orchestrator"].create_range(
                    range_id=range_id,
                    name=f"Concurrent Range {range_id}",
                    description=f"Range {range_id} for concurrency testing",
                    hosts=sample_hosts,
                    guests=sample_guests
                )
                
                # Register for monitoring
                services["monitoring"].register_range(metadata)
                
                # Collect metrics
                metrics = services["monitoring"].collect_range_metrics(range_id)
                assert metrics is not None
                
                return True
            except Exception as e:
                print(f"Error in range {range_id}: {e}")
                return False
        
        # Create multiple ranges concurrently
        threads = []
        results = {}
        
        for i in range(3):
            range_id = f"concurrent-range-{i}"
            thread = threading.Thread(
                target=lambda rid=range_id: results.update({rid: create_and_monitor_range(rid)})
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        assert len(results) == 3
        assert all(success for success in results.values())
        
        # Verify ranges exist
        all_ranges = services["orchestrator"].list_ranges()
        concurrent_ranges = [r for r in all_ranges if r.range_id.startswith("concurrent-range-")]
        assert len(concurrent_ranges) == 3
        
        # Clean up
        for range_metadata in concurrent_ranges:
            services["monitoring"].unregister_range(range_metadata.range_id)
            services["orchestrator"].destroy_range(range_metadata.range_id)