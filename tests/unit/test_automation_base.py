"""
Unit Tests for Automation Base Components

Tests the automation provider interfaces, configuration, and base functionality
without external dependencies.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch
from pathlib import Path

from cyris.infrastructure.automation import (
    AutomationProvider,
    AutomationResult,
    AutomationStatus,
    AutomationError,
    AutomationConfig
)
from cyris.config.automation_settings import (
    CyRISAutomationSettings,
    TerraformSettings,
    PackerSettings,
    VagrantSettings,
    ImageCacheSettings,
    AutomationGlobalSettings
)


class MockAutomationProvider(AutomationProvider):
    """Mock automation provider for testing"""
    
    def __init__(self, config: AutomationConfig, fail_operations: bool = False):
        super().__init__(config)
        self.fail_operations = fail_operations
        self.operation_history = []
    
    async def connect(self) -> None:
        """Mock connection"""
        if self.fail_operations:
            raise AutomationError("Connection failed")
        self._is_connected = True
    
    async def disconnect(self) -> None:
        """Mock disconnection"""
        self._is_connected = False
    
    async def validate_configuration(self) -> list[str]:
        """Mock configuration validation"""
        if self.fail_operations:
            return ["Mock validation error"]
        return []
    
    async def execute_operation(
        self, 
        operation_type: str,
        parameters: dict,
        operation_id: str = None
    ) -> AutomationResult:
        """Mock operation execution"""
        if not operation_id:
            operation_id = self.generate_operation_id()
        
        result = AutomationResult(
            operation_id=operation_id,
            provider_type=self.provider_type,
            status=AutomationStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        self._track_operation(result)
        self.operation_history.append((operation_type, parameters))
        
        if self.fail_operations:
            result.status = AutomationStatus.FAILED
            result.error_message = "Mock operation failed"
        else:
            result.status = AutomationStatus.COMPLETED
            result.output = f"Mock {operation_type} completed"
            result.artifacts = {"mock_artifact": "test_value"}
        
        result.completed_at = datetime.utcnow()
        return result
    
    async def get_operation_status(self, operation_id: str) -> AutomationResult:
        """Mock operation status"""
        return self._active_operations.get(operation_id)
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Mock operation cancellation"""
        if operation_id in self._active_operations:
            result = self._active_operations[operation_id]
            result.status = AutomationStatus.CANCELLED
            return True
        return False
    
    async def cleanup_artifacts(self, operation_id: str) -> None:
        """Mock artifact cleanup"""
        self._untrack_operation(operation_id)


class TestAutomationConfig:
    """Test automation configuration classes"""
    
    def test_automation_config_creation(self):
        """Test basic automation config creation"""
        config = AutomationConfig(
            provider_type="test_provider",
            enabled=True,
            timeout=1800,
            retry_count=5
        )
        
        assert config.provider_type == "test_provider"
        assert config.enabled is True
        assert config.timeout == 1800
        assert config.retry_count == 5
        assert config.working_directory is None
        assert config.environment_variables == {}
    
    def test_automation_config_with_defaults(self):
        """Test automation config with default values"""
        config = AutomationConfig(provider_type="test")
        
        assert config.enabled is True
        assert config.timeout == 3600
        assert config.retry_count == 3
        assert config.debug_mode is False


class TestAutomationResult:
    """Test automation result functionality"""
    
    def test_automation_result_creation(self):
        """Test automation result creation"""
        start_time = datetime.utcnow()
        result = AutomationResult(
            operation_id="test-123",
            provider_type="test_provider",
            status=AutomationStatus.RUNNING,
            started_at=start_time
        )
        
        assert result.operation_id == "test-123"
        assert result.provider_type == "test_provider"
        assert result.status == AutomationStatus.RUNNING
        assert result.started_at == start_time
        assert result.completed_at is None
        assert result.duration is None
    
    def test_automation_result_completion(self):
        """Test automation result completion tracking"""
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()
        
        result = AutomationResult(
            operation_id="test-123",
            provider_type="test_provider", 
            status=AutomationStatus.COMPLETED,
            started_at=start_time,
            completed_at=end_time,
            output="Operation completed successfully"
        )
        
        assert result.is_successful is True
        assert result.is_failed is False
        assert result.duration is not None
        assert result.duration >= 0
    
    def test_automation_result_failure(self):
        """Test automation result failure tracking"""
        result = AutomationResult(
            operation_id="test-123",
            provider_type="test_provider",
            status=AutomationStatus.FAILED,
            started_at=datetime.utcnow(),
            error_message="Operation failed"
        )
        
        assert result.is_successful is False
        assert result.is_failed is True
        assert result.error_message == "Operation failed"


class TestAutomationProvider:
    """Test automation provider base functionality"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock automation config"""
        return AutomationConfig(
            provider_type="mock_provider",
            timeout=300,
            retry_count=2
        )
    
    @pytest.fixture
    def mock_provider(self, mock_config):
        """Create mock automation provider"""
        return MockAutomationProvider(mock_config)
    
    @pytest.fixture
    def failing_provider(self, mock_config):
        """Create failing mock automation provider"""
        return MockAutomationProvider(mock_config, fail_operations=True)
    
    def test_provider_initialization(self, mock_provider):
        """Test provider initialization"""
        assert mock_provider.provider_type == "mock_provider"
        assert mock_provider.is_connected is False
        assert mock_provider.is_enabled is True
        assert len(mock_provider.get_active_operations()) == 0
    
    @pytest.mark.asyncio
    async def test_provider_connection(self, mock_provider):
        """Test provider connection"""
        assert mock_provider.is_connected is False
        
        await mock_provider.connect()
        assert mock_provider.is_connected is True
        
        await mock_provider.disconnect()
        assert mock_provider.is_connected is False
    
    @pytest.mark.asyncio
    async def test_provider_connection_failure(self, failing_provider):
        """Test provider connection failure"""
        with pytest.raises(AutomationError):
            await failing_provider.connect()
        
        assert failing_provider.is_connected is False
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, mock_provider, failing_provider):
        """Test configuration validation"""
        # Successful validation
        issues = await mock_provider.validate_configuration()
        assert isinstance(issues, list)
        assert len(issues) == 0
        
        # Failed validation
        issues = await failing_provider.validate_configuration()
        assert len(issues) > 0
        assert "Mock validation error" in issues
    
    @pytest.mark.asyncio
    async def test_operation_execution(self, mock_provider):
        """Test operation execution"""
        await mock_provider.connect()
        
        result = await mock_provider.execute_operation(
            operation_type="test_build",
            parameters={"param1": "value1"}
        )
        
        assert isinstance(result, AutomationResult)
        assert result.provider_type == "mock_provider"
        assert result.is_successful is True
        assert result.output == "Mock test_build completed"
        assert "mock_artifact" in result.artifacts
        
        # Check operation was tracked
        active_ops = mock_provider.get_active_operations()
        assert len(active_ops) == 1
        assert active_ops[0].operation_id == result.operation_id
    
    @pytest.mark.asyncio
    async def test_operation_failure(self, failing_provider):
        """Test operation failure handling"""
        # For failing provider, we expect connection to fail, but let's bypass that for operation testing
        failing_provider._is_connected = True
        
        result = await failing_provider.execute_operation(
            operation_type="test_build", 
            parameters={}
        )
        
        assert result.is_failed is True
        assert result.error_message == "Mock operation failed"
    
    @pytest.mark.asyncio
    async def test_operation_cancellation(self, mock_provider):
        """Test operation cancellation"""
        await mock_provider.connect()
        
        result = await mock_provider.execute_operation(
            operation_type="long_running",
            parameters={}
        )
        
        # Cancel the operation
        cancelled = await mock_provider.cancel_operation(result.operation_id)
        assert cancelled is True
        
        # Check status was updated
        updated_result = await mock_provider.get_operation_status(result.operation_id)
        assert updated_result.status == AutomationStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_provider, failing_provider):
        """Test provider health check"""
        # Healthy provider
        health = await mock_provider.health_check()
        assert health['provider_type'] == 'mock_provider'
        assert health['status'] == 'healthy'
        assert health['connected'] is True
        assert health['validation_issues'] == []
        
        # Unhealthy provider
        health = await failing_provider.health_check()
        assert health['status'] == 'unhealthy'
        assert health['connected'] is False
        assert 'error' in health
    
    def test_operation_id_generation(self, mock_provider):
        """Test operation ID generation"""
        op_id1 = mock_provider.generate_operation_id()
        op_id2 = mock_provider.generate_operation_id()
        
        assert op_id1 != op_id2
        assert op_id1.startswith("mock_provider-")
        assert len(op_id1.split("-")[1]) == 8  # UUID prefix length


class TestAutomationSettings:
    """Test automation configuration settings"""
    
    def test_terraform_settings_defaults(self):
        """Test Terraform settings default values"""
        settings = TerraformSettings()
        
        assert settings.enabled is True
        assert settings.timeout == 3600
        assert settings.retry_count == 3
        assert settings.parallelism == 4
        assert settings.libvirt_uri == "qemu:///system"
        assert settings.aws_region == "us-west-2"
        assert settings.auto_approve is False
    
    def test_packer_settings_defaults(self):
        """Test Packer settings default values"""
        settings = PackerSettings()
        
        assert settings.enabled is True
        assert settings.timeout == 7200
        assert settings.parallel_builds == 1
        assert settings.cache_enabled is True
        assert settings.cache_retention_days == 30
        assert "qcow2" in settings.output_formats
        assert settings.qemu_accelerator == "kvm"
    
    def test_vagrant_settings_defaults(self):
        """Test Vagrant settings default values"""
        settings = VagrantSettings()
        
        assert settings.enabled is False  # Disabled by default
        assert settings.default_provider == "libvirt"
        assert settings.box_update_check is True
        assert settings.sync_folders is True
        assert settings.gui_enabled is False
    
    def test_image_cache_settings_defaults(self):
        """Test image cache settings default values"""
        settings = ImageCacheSettings()
        
        assert settings.enabled is True
        assert settings.max_cache_size_gb == 50
        assert settings.retention_days == 30
        assert settings.concurrent_downloads == 3
        assert settings.verify_checksums is True
        assert "ubuntu.com" in settings.ubuntu_mirror
    
    @patch.dict('os.environ', {
        'CYRIS_TERRAFORM_ENABLED': 'false',
        'CYRIS_PACKER_TIMEOUT': '3600',
        'CYRIS_AUTOMATION_FAIL_FAST': 'true'
    })
    def test_environment_variable_override(self):
        """Test configuration override from environment variables"""
        settings = CyRISAutomationSettings()
        
        assert settings.terraform.enabled is False
        assert settings.packer.timeout == 3600
        assert settings.automation.fail_fast is True
    
    def test_cyris_automation_settings_integration(self):
        """Test full CyRIS automation settings"""
        settings = CyRISAutomationSettings()
        
        # Test automation status
        status = settings.get_automation_status()
        assert 'terraform_enabled' in status
        assert 'packer_enabled' in status
        assert 'automation_enabled' in status
        
        # Test enabled providers
        enabled = settings.get_enabled_providers()
        assert 'terraform' in enabled
        assert 'packer' in enabled
        # vagrant should not be in enabled by default
        assert 'vagrant' not in enabled