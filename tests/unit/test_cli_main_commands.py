#!/usr/bin/env python3

"""
全面的CLI命令测试 - 用于重构前的功能保护
Following TDD principles: 确保重构时不丢失功能
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
from datetime import datetime

import sys
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.cli.main import (
    cli, create, list, status, destroy, rm, 
    config_show, config_init, validate, ssh_info, setup_permissions
)
from cyris.services.orchestrator import RangeStatus, RangeMetadata
from cyris.config.settings import CyRISSettings


class TestCLIMainFunctions:
    """测试主要CLI功能以保护重构"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @pytest.fixture 
    def mock_config(self):
        """Mock配置对象"""
        config = Mock(spec=CyRISSettings)
        config.cyris_path = Path("/test/cyris")
        config.cyber_range_dir = Path("/test/cyber_range") 
        config.gw_mode = False
        config.gw_account = None
        config.gw_mgmt_addr = None
        config.user_email = None
        return config
    
    @pytest.fixture
    def mock_range_metadata(self):
        """Mock靶场元数据"""
        return RangeMetadata(
            range_id="test_range_123",
            name="Test Range",
            description="Test cyber range",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE,
            owner="test_user",
            tags={"environment": "testing"},
            last_modified=datetime.now(),
            provider_config={"libvirt_uri": "qemu:///system"}
        )


class TestCreateCommand(TestCLIMainFunctions):
    """测试create命令功能"""
    
    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_create_dry_run_success(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config):
        """测试干运行模式创建成功"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.create_range_from_yaml.return_value = "test_range_123"
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # 创建临时YAML文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("test: yaml")
            yaml_file = f.name
        
        try:
            result = runner.invoke(create, [yaml_file, '--dry-run'])
            assert result.exit_code == 0
            assert "Dry run mode" in result.output
            assert "Validation successful" in result.output
            mock_orchestrator.create_range_from_yaml.assert_called_once()
        finally:
            Path(yaml_file).unlink(missing_ok=True)

    @patch('cyris.cli.main.get_config') 
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_create_dry_run_failure(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config):
        """测试干运行模式创建失败"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.create_range_from_yaml.return_value = None  # 失败
        mock_orchestrator_class.return_value = mock_orchestrator
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("test: yaml")
            yaml_file = f.name
        
        try:
            result = runner.invoke(create, [yaml_file, '--dry-run'])
            assert result.exit_code == 1
            assert "Validation failed" in result.output
        finally:
            Path(yaml_file).unlink(missing_ok=True)


class TestListCommand(TestCLIMainFunctions):
    """测试list命令功能"""
    
    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_list_no_ranges(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config):
        """测试没有靶场时的列表显示"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.list_ranges.return_value = []
        mock_orchestrator_class.return_value = mock_orchestrator
        mock_config.cyber_range_dir.exists.return_value = True
        mock_config.cyber_range_dir.iterdir.return_value = []
        
        result = runner.invoke(list)
        assert result.exit_code == 0
        assert "No cyber ranges found" in result.output

    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_list_with_ranges(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config, mock_range_metadata):
        """测试有靶场时的列表显示"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.list_ranges.return_value = [mock_range_metadata]
        mock_orchestrator_class.return_value = mock_orchestrator
        
        result = runner.invoke(list)
        assert result.exit_code == 0
        assert "Test Range" in result.output
        assert "test_range_123" in result.output

    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_list_specific_range(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config, mock_range_metadata):
        """测试列出特定靶场"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.get_range.return_value = mock_range_metadata
        mock_orchestrator_class.return_value = mock_orchestrator
        
        result = runner.invoke(list, ['--range-id', '123'])
        assert result.exit_code == 0
        assert "Test Range" in result.output


class TestStatusCommand(TestCLIMainFunctions):
    """测试status命令功能"""
    
    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_status_range_exists(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config, mock_range_metadata):
        """测试查看存在靶场的状态"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.get_range.return_value = mock_range_metadata
        mock_orchestrator.get_range_resources.return_value = {
            'hosts': ['host1'], 
            'guests': ['guest1', 'guest2']
        }
        mock_orchestrator_class.return_value = mock_orchestrator
        mock_config.cyber_range_dir.__truediv__.return_value.exists.return_value = True
        
        result = runner.invoke(status, ['test_range_123'])
        assert result.exit_code == 0
        assert "Test Range" in result.output
        assert "ACTIVE" in result.output

    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_status_range_not_found(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config):
        """测试查看不存在靶场的状态"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.get_range.return_value = None
        mock_orchestrator_class.return_value = mock_orchestrator
        mock_config.cyber_range_dir.__truediv__.return_value.exists.return_value = False
        
        result = runner.invoke(status, ['nonexistent'])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestConfigCommands(TestCLIMainFunctions):
    """测试配置相关命令"""
    
    @patch('cyris.cli.main.get_config')
    def test_config_show(self, mock_get_config, runner, mock_config):
        """测试显示配置"""
        mock_get_config.return_value = mock_config
        
        result = runner.invoke(config_show)
        assert result.exit_code == 0
        assert "Current configuration" in result.output
        assert str(mock_config.cyris_path) in result.output

    @patch('cyris.config.parser.create_default_config')
    def test_config_init_success(self, mock_create_config, runner):
        """测试初始化配置成功"""
        mock_settings = Mock()
        mock_create_config.return_value = mock_settings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yml"
            
            result = runner.invoke(config_init, ['--output', str(config_path)])
            assert result.exit_code == 0
            assert "Default configuration file created" in result.output

    @patch('cyris.config.parser.create_default_config')
    def test_config_init_overwrite_prompt(self, mock_create_config, runner):
        """测试配置文件已存在时的覆盖提示"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("existing: config")
            config_path = f.name
        
        try:
            # 取消覆盖
            result = runner.invoke(config_init, ['--output', config_path], input='n\n')
            assert result.exit_code == 0
            assert "Operation cancelled" in result.output
        finally:
            Path(config_path).unlink(missing_ok=True)


class TestValidateCommand(TestCLIMainFunctions):
    """测试validate命令"""
    
    @patch('cyris.cli.main.get_config')
    def test_validate_success(self, mock_get_config, runner, mock_config):
        """测试环境验证成功"""
        mock_get_config.return_value = mock_config
        mock_config.cyris_path.exists.return_value = True
        mock_config.cyber_range_dir.exists.return_value = True
        
        result = runner.invoke(validate)
        assert result.exit_code == 0
        assert "Environment validation passed" in result.output

    @patch('cyris.cli.main.get_config') 
    def test_validate_failure(self, mock_get_config, runner, mock_config):
        """测试环境验证失败"""
        mock_get_config.return_value = mock_config
        mock_config.cyris_path.exists.return_value = False  # 路径不存在
        mock_config.cyber_range_dir.exists.return_value = True
        
        result = runner.invoke(validate)
        assert result.exit_code == 1
        assert "CyRIS path does not exist" in result.output


# 为了保护SSH Info和Setup Permissions等复杂功能
class TestComplexCommands(TestCLIMainFunctions):
    """测试复杂命令的基本行为"""
    
    @patch('cyris.cli.main.get_config')
    @patch('cyris.services.orchestrator.RangeOrchestrator')
    @patch('cyris.infrastructure.providers.kvm_provider.KVMProvider')
    def test_ssh_info_range_not_found(self, mock_kvm, mock_orchestrator_class, mock_get_config, runner, mock_config):
        """测试SSH信息查询 - 靶场不存在"""
        mock_get_config.return_value = mock_config
        mock_orchestrator = Mock()
        mock_orchestrator.get_range.return_value = None
        mock_orchestrator_class.return_value = mock_orchestrator
        
        result = runner.invoke(ssh_info, ['nonexistent'])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch('cyris.infrastructure.permissions.PermissionManager')
    @patch('cyris.cli.main.get_config')
    def test_setup_permissions_dry_run(self, mock_get_config, mock_permission_manager, runner, mock_config):
        """测试权限设置干运行"""
        mock_get_config.return_value = mock_config
        mock_manager = Mock()
        mock_manager.check_libvirt_compatibility.return_value = {
            'libvirt_user': 'libvirt-qemu',
            'acl_supported': True,
            'current_user_groups': ['users'],
            'recommendations': []
        }
        mock_permission_manager.return_value = mock_manager
        
        result = runner.invoke(setup_permissions, ['--dry-run'])
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output