"""
端到端测试 - gw_mode功能完整验证
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.config.settings import CyRISSettings
from cyris.services.orchestrator import RangeOrchestrator
from cyris.services.gateway_service import GatewayService, EntryPointInfo
from cyris.infrastructure.network.tunnel_manager import TunnelManager
from cyris.core.exceptions import GatewayError


class TestGwModeE2E:
    """gw_mode端到端测试"""
    
    @pytest.fixture
    def sample_yaml_config(self):
        """示例YAML配置"""
        return {
            'host_settings': [
                {
                    'id': 'host_1',
                    'mgmt_addr': '10.0.1.100',
                    'account': 'ubuntu'
                }
            ],
            'guest_settings': [
                {
                    'id': 'desktop',
                    'basevm_host': 'host_1',
                    'basevm_type': 'kvm'
                }
            ],
            'clone_settings': [
                {
                    'range_id': 123,
                    'hosts': [
                        {
                            'host_id': 'host_1',
                            'instance_number': 2,
                            'guests': [
                                {
                                    'guest_id': 'desktop',
                                    'number': 1,
                                    'entry_point': True
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    
    def test_direct_mode_full_workflow(self, sample_yaml_config):
        """测试直接模式完整工作流程"""
        # 直接模式配置
        settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=False
        )
        
        # 模拟基础设施提供商
        mock_providers = {'kvm': Mock(), 'aws': Mock()}
        
        # 创建编排器
        orchestrator = RangeOrchestrator(settings, mock_providers)
        
        # 模拟隧道创建成功
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
            
            # 创建网络靶场
            result = orchestrator.create_cyber_range(sample_yaml_config)
            
            # 验证创建成功
            assert result['success'] is True
            assert result['range_id'] == 123
            assert 'entry_points' in result
            assert len(result['entry_points']) == 2  # 2个实例
            
            # 验证入口点配置（直接模式）
            entry_points = result['entry_points']
            for ep in entry_points:
                assert ep['access_host'] == '10.0.1.100'  # 直接访问主机
                assert 60000 <= ep['access_port'] <= 65000  # 端口范围
                assert ep['account'] == 'trainee'
                assert len(ep['password']) == 12  # 随机密码长度
            
            # 获取访问通知
            notification = orchestrator.get_access_notification(123)
            assert "Range ID: 123" in notification
            assert "Entry Point #1:" in notification
            assert "Entry Point #2:" in notification
            assert "Mode: Direct" in notification
            
            # 验证系统状态
            status = orchestrator.get_system_status()
            assert status['gateway_service']['gw_mode'] is False
            assert status['gateway_service']['total_entry_points'] == 2
            assert status['gateway_service']['active_tunnels'] == 2
            
            # 销毁网络靶场
            destroy_result = orchestrator.destroy_cyber_range(123)
            assert destroy_result['success'] is True
            assert destroy_result['range_id'] == 123
            
            # 验证清理后状态
            final_status = orchestrator.get_system_status()
            assert final_status['gateway_service']['total_entry_points'] == 0
            assert final_status['gateway_service']['active_tunnels'] == 0
    
    def test_gateway_mode_full_workflow(self, sample_yaml_config):
        """测试网关模式完整工作流程"""
        # 网关模式配置
        settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=True,
            gw_account="gateway_user",
            gw_mgmt_addr="gateway.example.com",
            gw_inside_addr="172.16.1.1"
        )
        
        # 模拟基础设施提供商
        mock_providers = {'kvm': Mock(), 'aws': Mock()}
        
        # 创建编排器
        orchestrator = RangeOrchestrator(settings, mock_providers)
        
        # 模拟隧道创建成功（网关模式需要两个命令）
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
            
            # 创建网络靶场
            result = orchestrator.create_cyber_range(sample_yaml_config)
            
            # 验证创建成功
            assert result['success'] is True
            assert result['range_id'] == 123
            assert 'entry_points' in result
            assert len(result['entry_points']) == 2  # 2个实例
            
            # 验证入口点配置（网关模式）
            entry_points = result['entry_points']
            for ep in entry_points:
                assert ep['access_host'] == 'gateway.example.com'  # 通过网关访问
                assert 60000 <= ep['access_port'] <= 65000
                assert ep['account'] == 'trainee'
                assert len(ep['password']) == 12
            
            # 获取访问通知
            notification = orchestrator.get_access_notification(123)
            assert "Range ID: 123" in notification
            assert "ssh trainee@gateway.example.com" in notification  # 网关地址
            assert "Mode: Gateway" in notification
            
            # 验证系统状态包含网关配置
            status = orchestrator.get_system_status()
            assert status['gateway_service']['gw_mode'] is True
            assert status['gateway_service']['gateway_config']['account'] == 'gateway_user'
            assert status['gateway_service']['gateway_config']['mgmt_addr'] == 'gateway.example.com'
            
            # 验证SSH命令被正确调用（网关 + 本地隧道）
            # 网关模式应该调用多个subprocess.run
            assert mock_subprocess.call_count >= 2  # 至少2个实例 * 2个隧道
    
    def test_mixed_configuration_validation(self):
        """测试混合配置验证"""
        # 无效的网关配置（缺少必要参数）
        invalid_settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=True,
            gw_account="gateway_user"
            # 缺少gw_mgmt_addr和gw_inside_addr
        )
        
        mock_providers = {'kvm': Mock()}
        orchestrator = RangeOrchestrator(invalid_settings, mock_providers)
        
        # 验证网关配置应该失败
        with pytest.raises(GatewayError, match="Gateway mode requires"):
            orchestrator.gateway_service.validate_gateway_settings()
    
    def test_concurrent_ranges_isolation(self, sample_yaml_config):
        """测试并发靶场的隔离性"""
        settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=False
        )
        
        mock_providers = {'kvm': Mock()}
        orchestrator = RangeOrchestrator(settings, mock_providers)
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
            
            # 创建第一个靶场
            config1 = sample_yaml_config.copy()
            config1['clone_settings'][0]['range_id'] = 123
            result1 = orchestrator.create_cyber_range(config1)
            
            # 创建第二个靶场
            config2 = sample_yaml_config.copy()
            config2['clone_settings'][0]['range_id'] = 456
            result2 = orchestrator.create_cyber_range(config2)
            
            # 验证两个靶场都成功创建
            assert result1['success'] is True
            assert result2['success'] is True
            assert result1['range_id'] == 123
            assert result2['range_id'] == 456
            
            # 验证端口不冲突
            ports1 = [ep['access_port'] for ep in result1['entry_points']]
            ports2 = [ep['access_port'] for ep in result2['entry_points']]
            assert len(set(ports1) & set(ports2)) == 0  # 无端口冲突
            
            # 验证系统状态
            status = orchestrator.get_system_status()
            assert status['gateway_service']['total_entry_points'] == 4  # 2个靶场 * 2个入口点
            assert status['gateway_service']['ranges'] == 2
            
            # 销毁第一个靶场
            destroy_result1 = orchestrator.destroy_cyber_range(123)
            assert destroy_result1['success'] is True
            
            # 验证第二个靶场仍然存在
            status_after = orchestrator.get_system_status()
            assert status_after['gateway_service']['total_entry_points'] == 2
            assert status_after['gateway_service']['ranges'] == 1
            
            # 第二个靶场的通知应该仍然正常
            notification2 = orchestrator.get_access_notification(456)
            assert "Range ID: 456" in notification2
    
    def test_error_recovery_and_cleanup(self, sample_yaml_config):
        """测试错误恢复和清理"""
        settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=False
        )
        
        mock_providers = {'kvm': Mock()}
        orchestrator = RangeOrchestrator(settings, mock_providers)
        
        # 模拟隧道创建失败
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Connection failed")
            
            # 创建应该失败
            result = orchestrator.create_cyber_range(sample_yaml_config)
            
            # 验证创建失败
            assert result['success'] is False
            assert 'error' in result
            
            # 验证失败后系统状态清洁
            status = orchestrator.get_system_status()
            assert status['gateway_service']['total_entry_points'] == 0
            assert status['gateway_service']['active_tunnels'] == 0
    
    def test_configuration_compatibility(self):
        """测试配置兼容性"""
        # 测试传统INI格式配置的解析
        from cyris.config.parser import parse_legacy_config
        
        # 创建临时配置文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("""[config]
cyris_path = /tmp/cyris/
cyber_range_dir = /tmp/cyris/cyber_range/
gw_mode = on
gw_account = test_gateway
gw_mgmt_addr = test.gateway.com
gw_inside_addr = 172.16.1.1
user_email = test@example.com
""")
            config_file = f.name
        
        try:
            # 解析配置
            result = parse_legacy_config(config_file)
            abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email = result
            
            # 验证解析结果
            assert abs_path == "/tmp/cyris/"
            assert cr_dir == "/tmp/cyris/cyber_range/"
            assert gw_mode is True  # "on" 应该被解析为 True
            assert gw_account == "test_gateway"
            assert gw_mgmt_addr == "test.gateway.com"
            assert gw_inside_addr == "172.16.1.1"
            assert user_email == "test@example.com"
            
        finally:
            # 清理临时文件
            os.unlink(config_file)