"""
Unit Tests for Terraform Infrastructure Builder

Tests the Terraform automation provider functionality including configuration generation,
infrastructure planning, and deployment execution without requiring actual Terraform installation.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from cyris.infrastructure.automation.terraform_builder import (
    TerraformBuilder,
    TerraformError,
    StateManager
)
from cyris.infrastructure.automation import (
    AutomationStatus,
    AutomationResult
)
from cyris.config.automation_settings import TerraformSettings


class TestTerraformBuilder:
    """Test Terraform builder functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def terraform_settings(self, temp_dir):
        """Create test Terraform settings"""
        return TerraformSettings(
            enabled=True,
            working_dir=temp_dir / "working",
            templates_dir=temp_dir / "templates", 
            state_dir=temp_dir / "state",
            timeout=300,
            retry_count=2,
            parallelism=1,
            libvirt_uri="qemu:///system"
        )
    
    @pytest.fixture
    def mock_terraform_binary(self, temp_dir):
        """Create mock terraform binary"""
        terraform_binary = temp_dir / "terraform"
        terraform_binary.touch()
        terraform_binary.chmod(0o755)
        return terraform_binary
    
    @pytest.fixture
    def terraform_builder(self, terraform_settings, mock_terraform_binary):
        """Create Terraform builder with mocked binary"""
        with patch.object(TerraformBuilder, '_find_terraform_binary', return_value=mock_terraform_binary):
            builder = TerraformBuilder(terraform_settings)
            return builder
    
    def test_terraform_builder_initialization(self, terraform_builder, terraform_settings):
        """Test Terraform builder initialization"""
        assert terraform_builder.provider_type == "terraform"
        assert terraform_builder.is_enabled is True
        assert terraform_builder.settings == terraform_settings
        assert terraform_builder.terraform_binary is not None
        assert isinstance(terraform_builder.state_manager, StateManager)
    
    def test_find_terraform_binary_success(self, temp_dir):
        """Test finding Terraform binary in system"""
        # Create mock binary in temp location
        mock_binary = temp_dir / "terraform"
        mock_binary.touch()
        mock_binary.chmod(0o755)
        
        settings = TerraformSettings(binary_path=mock_binary)
        builder = TerraformBuilder(settings)
        
        assert builder.terraform_binary == mock_binary
    
    def test_find_terraform_binary_not_found(self, terraform_settings):
        """Test handling when Terraform binary not found"""
        with patch.object(TerraformBuilder, '_find_terraform_binary', return_value=None):
            builder = TerraformBuilder(terraform_settings)
            assert builder.terraform_binary is None
    
    @pytest.mark.asyncio
    async def test_connect_success(self, terraform_builder):
        """Test successful connection to Terraform"""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Terraform v1.6.0", b""))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            await terraform_builder.connect()
            
            assert terraform_builder.is_connected is True
    
    @pytest.mark.asyncio
    async def test_connect_binary_not_found(self, terraform_settings):
        """Test connection failure when binary not found"""
        with patch.object(TerraformBuilder, '_find_terraform_binary', return_value=None):
            builder = TerraformBuilder(terraform_settings)
            
            with pytest.raises(TerraformError, match="Terraform binary not found"):
                await builder.connect()
    
    @pytest.mark.asyncio
    async def test_connect_version_check_failed(self, terraform_builder):
        """Test connection failure when version check fails"""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Command not found"))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            with pytest.raises(TerraformError, match="version check failed"):
                await terraform_builder.connect()
    
    @pytest.mark.asyncio
    async def test_validate_configuration_success(self, terraform_builder):
        """Test successful configuration validation"""
        with patch('shutil.disk_usage', return_value=Mock(free=10*1024**3)):  # 10GB free
            with patch('shutil.which', return_value="/usr/bin/tool"):
                with patch('subprocess.run', return_value=Mock(returncode=0, stdout="", stderr="")):
                    issues = await terraform_builder.validate_configuration()
                    assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_configuration_issues(self, terraform_builder):
        """Test configuration validation with issues"""
        with patch('shutil.disk_usage', return_value=Mock(free=0.5*1024**3)):  # 0.5GB free (insufficient)
            with patch('shutil.which', return_value=None):  # Missing tools
                with patch('subprocess.run', return_value=Mock(returncode=1)):  # Libvirt connection failed
                    issues = await terraform_builder.validate_configuration()
                    
                    assert len(issues) > 0
                    assert any("disk space" in issue.lower() for issue in issues)
                    assert any("missing" in issue.lower() for issue in issues)
                    assert any("libvirt" in issue.lower() for issue in issues)
    
    @pytest.mark.asyncio  
    async def test_execute_apply_operation_success(self, terraform_builder):
        """Test successful apply operation"""
        # Mock all Terraform operations
        with patch.object(terraform_builder, '_generate_terraform_config', AsyncMock(return_value="mock config")):
            with patch.object(terraform_builder, '_run_terraform_init', AsyncMock(return_value="Terraform initialized")):
                with patch.object(terraform_builder, '_run_terraform_plan', AsyncMock(return_value="Plan: 2 to add")):
                    with patch.object(terraform_builder, '_run_terraform_apply', AsyncMock(return_value="Apply complete")):
                        with patch.object(terraform_builder, '_get_terraform_state', AsyncMock(return_value={"version": 4, "resources": []})):
                            
                            parameters = {
                                "hosts": [Mock(name="host1")],
                                "guests": [Mock(name="guest1")],
                                "network_config": {"default": {"subnet": "192.168.1.0/24"}}
                            }
                            
                            result = await terraform_builder.execute_operation("apply", parameters)
                            
                            assert result.status == AutomationStatus.COMPLETED
                            assert result.output == "Apply complete"
                            assert "workspace_dir" in result.artifacts
                            assert "resources_created" in result.artifacts
    
    @pytest.mark.asyncio
    async def test_execute_apply_operation_failure(self, terraform_builder):
        """Test apply operation failure"""
        # Mock operation failure
        with patch.object(terraform_builder, '_generate_terraform_config', AsyncMock(side_effect=TerraformError("Config generation failed"))):
            
            parameters = {
                "hosts": [Mock(name="host1")],
                "guests": [Mock(name="guest1")]
            }
            
            result = await terraform_builder.execute_operation("apply", parameters)
            
            assert result.status == AutomationStatus.FAILED
            assert "Config generation failed" in result.error_message
    
    @pytest.mark.asyncio
    async def test_execute_plan_operation(self, terraform_builder):
        """Test plan operation"""
        mock_workspace = terraform_builder.settings.working_dir / "test-workspace"
        mock_workspace.mkdir(parents=True, exist_ok=True)
        
        with patch.object(terraform_builder, '_run_terraform_plan', AsyncMock(return_value="Plan: 1 to add, 0 to change")):
            parameters = {"workspace_dir": str(mock_workspace)}
            result = await terraform_builder.execute_operation("plan", parameters)
            
            assert result.status == AutomationStatus.COMPLETED
            assert "Plan: 1 to add" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_destroy_operation(self, terraform_builder):
        """Test destroy operation"""
        mock_workspace = terraform_builder.settings.working_dir / "test-workspace"
        mock_workspace.mkdir(parents=True, exist_ok=True)
        
        with patch.object(terraform_builder, '_run_terraform_destroy', AsyncMock(return_value="Destroy complete")):
            parameters = {"workspace_dir": str(mock_workspace)}
            result = await terraform_builder.execute_operation("destroy", parameters)
            
            assert result.status == AutomationStatus.COMPLETED
            assert "Destroy complete" in result.output
    
    @pytest.mark.asyncio
    async def test_execute_validate_operation(self, terraform_builder):
        """Test validate operation"""
        config_path = terraform_builder.settings.working_dir / "test.tf"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("# Test configuration")
        
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Success! The configuration is valid", b""))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            parameters = {"config_path": str(config_path)}
            result = await terraform_builder.execute_operation("validate", parameters)
            
            assert result.status == AutomationStatus.COMPLETED
            assert "valid" in result.output.lower()
    
    @pytest.mark.asyncio
    async def test_generate_terraform_config(self, terraform_builder):
        """Test Terraform configuration generation"""
        # Create mock hosts and guests
        mock_host = Mock()
        mock_host.name = "test-host"
        
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        mock_guest.memory = 2048
        mock_guest.vcpus = 2
        mock_guest.base_image = "ubuntu-22.04.qcow2"
        
        hosts = [mock_host]
        guests = [mock_guest]
        network_config = {
            "default": {
                "subnet": "192.168.1.0/24",
                "domain": "test.local"
            }
        }
        
        config = await terraform_builder._generate_terraform_config(hosts, guests, network_config, "test-op")
        
        assert "libvirt" in config
        assert "test-vm" in config
        assert "192.168.1.0/24" in config
        assert "test.local" in config
        assert "memory = 2048" in config
    
    def test_generate_default_template(self, terraform_builder):
        """Test default template generation"""
        template = terraform_builder._generate_default_template()
        
        assert "terraform" in template
        assert "libvirt" in template
        assert "dmacvicar/libvirt" in template
        assert "qemu:///system" in template
    
    def test_generate_network_resource(self, terraform_builder):
        """Test network resource generation"""
        network_info = {
            "subnet": "10.1.0.0/24",
            "domain": "example.local"
        }
        
        resource = terraform_builder._generate_network_resource("test-network", network_info)
        
        assert 'resource "libvirt_network" "test-network"' in resource
        assert "10.1.0.0/24" in resource
        assert "example.local" in resource
        assert "dhcp" in resource
        assert "dns" in resource
    
    def test_generate_guest_resource(self, terraform_builder):
        """Test guest VM resource generation"""
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        mock_guest.memory = 4096
        mock_guest.vcpus = 4
        mock_guest.base_image = "centos-8.qcow2"
        
        resource = terraform_builder._generate_guest_resource(mock_guest)
        
        assert 'resource "libvirt_volume" "test-vm_disk"' in resource
        assert 'resource "libvirt_domain" "test-vm"' in resource
        assert "memory = 4096" in resource
        assert "vcpu   = 4" in resource
    
    def test_extract_created_resources(self, terraform_builder):
        """Test resource extraction from Terraform state"""
        mock_state = {
            "version": 4,
            "resources": [
                {
                    "type": "libvirt_network",
                    "name": "default",
                    "provider": "registry.terraform.io/dmacvicar/libvirt",
                    "instances": [{"attributes": {"id": "net-001"}}]
                },
                {
                    "type": "libvirt_domain", 
                    "name": "test-vm",
                    "provider": "registry.terraform.io/dmacvicar/libvirt",
                    "instances": [{"attributes": {"id": "vm-001"}}]
                }
            ]
        }
        
        resources = terraform_builder._extract_created_resources(mock_state)
        
        assert len(resources) == 2
        assert resources[0]["type"] == "libvirt_network"
        assert resources[0]["name"] == "default"
        assert resources[1]["type"] == "libvirt_domain"
        assert resources[1]["name"] == "test-vm"
    
    @pytest.mark.asyncio
    async def test_operation_tracking(self, terraform_builder):
        """Test operation tracking functionality"""
        # Start operation
        parameters = {"hosts": [Mock(name="test")], "guests": []}
        
        # Mock to avoid actual execution
        with patch.object(terraform_builder, '_execute_apply', AsyncMock()):
            result = await terraform_builder.execute_operation("apply", parameters)
            
            # Should be tracked during execution
            assert result.operation_id in terraform_builder._active_operations
            
            # Clean up
            await terraform_builder.cleanup_artifacts(result.operation_id)
            assert result.operation_id not in terraform_builder._active_operations


class TestStateManager:
    """Test Terraform state management functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def state_settings(self, temp_dir):
        """Create state manager settings"""
        return TerraformSettings(
            state_dir=temp_dir,
            working_dir=temp_dir / "working"
        )
    
    @pytest.fixture
    def state_manager(self, state_settings):
        """Create state manager instance"""
        return StateManager(state_settings)
    
    @pytest.mark.asyncio
    async def test_sync_state(self, state_manager):
        """Test state synchronization"""
        result = await state_manager.sync_state("test-workspace")
        
        # Currently returns empty dict (placeholder implementation)
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_backup_state(self, state_manager):
        """Test state backup"""
        backup_path = await state_manager.backup_state("test-workspace")
        
        assert backup_path.name == "test-workspace.backup"
        assert backup_path.parent == state_manager.state_dir
    
    @pytest.mark.asyncio
    async def test_restore_state(self, state_manager, temp_dir):
        """Test state restoration"""
        backup_path = temp_dir / "test-backup.tfstate"
        backup_path.write_text('{"version": 4, "resources": []}')
        
        result = await state_manager.restore_state("test-workspace", backup_path)
        
        # Currently returns True (placeholder implementation)
        assert result is True


class TestTerraformIntegration:
    """Integration tests for Terraform builder (mocked)"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.mark.asyncio
    async def test_end_to_end_terraform_workflow(self, temp_dir):
        """Test complete Terraform workflow from start to finish"""
        # Setup
        settings = TerraformSettings(
            working_dir=temp_dir / "working",
            templates_dir=temp_dir / "templates",
            state_dir=temp_dir / "state",
            timeout=60
        )
        
        # Create mock Terraform binary
        mock_binary = temp_dir / "terraform"
        mock_binary.touch()
        mock_binary.chmod(0o755)
        
        with patch.object(TerraformBuilder, '_find_terraform_binary', return_value=mock_binary):
            builder = TerraformBuilder(settings)
            
            # Mock all external dependencies
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Terraform v1.6.0", b""))
            
            with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
                with patch.object(builder, '_run_terraform_init', AsyncMock(return_value="Terraform initialized")):
                    with patch.object(builder, '_run_terraform_plan', AsyncMock(return_value="Plan: 2 to add")):
                        with patch.object(builder, '_run_terraform_apply', AsyncMock(return_value="Apply complete")):
                            with patch.object(builder, '_get_terraform_state', AsyncMock(return_value={"version": 4, "resources": []})):
                                
                                # Connect
                                await builder.connect()
                                assert builder.is_connected
                                
                                # Validate configuration
                                with patch('shutil.disk_usage', return_value=Mock(free=10*1024**3)):
                                    with patch('shutil.which', return_value="/usr/bin/tool"):
                                        with patch('subprocess.run', return_value=Mock(returncode=0)):
                                            issues = await builder.validate_configuration()
                                            assert len(issues) == 0
                                
                                # Execute apply
                                parameters = {
                                    "hosts": [Mock(name="host1")],
                                    "guests": [Mock(name="guest1")],
                                    "network_config": {"default": {"subnet": "192.168.1.0/24"}}
                                }
                                
                                result = await builder.execute_operation("apply", parameters)
                                
                                assert result.status == AutomationStatus.COMPLETED
                                assert result.output == "Apply complete"
                                assert "workspace_dir" in result.artifacts
                                
                                # Cleanup
                                await builder.cleanup_artifacts(result.operation_id)
                                await builder.disconnect()