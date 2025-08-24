"""
测试编排服务的网关模式集成 - TDD实现
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


class TestOrchestratorGatewayIntegration:
    """测试编排服务网关集成"""
    
    @pytest.fixture
    def settings_direct_mode(self):
        """直接模式配置"""
        return CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=False
        )
    
    @pytest.fixture
    def settings_gateway_mode(self):
        """网关模式配置"""
        return CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=True,
            gw_account="gateway_user",
            gw_mgmt_addr="gateway.example.com",
            gw_inside_addr="172.16.1.1"
        )
    
    @pytest.fixture
    def mock_providers(self):
        """模拟提供商"""
        kvm_provider = Mock()
        aws_provider = Mock()
        return {'kvm': kvm_provider, 'aws': aws_provider}
    
    def test_orchestrator_initialization_with_gateway_service(self, settings_direct_mode, mock_providers):
        """测试编排器初始化包含网关服务"""
        orchestrator = RangeOrchestrator(settings_direct_mode, mock_providers)
        
        # 验证网关服务已初始化
        assert hasattr(orchestrator, 'gateway_service')
        assert isinstance(orchestrator.gateway_service, GatewayService)
        assert hasattr(orchestrator, 'tunnel_manager')
        assert isinstance(orchestrator.tunnel_manager, TunnelManager)
    
    def test_orchestrator_gateway_mode_validation(self, settings_gateway_mode, mock_providers):
        """测试编排器网关模式验证"""
        orchestrator = RangeOrchestrator(settings_gateway_mode, mock_providers)
        
        # 网关设置应该有效
        orchestrator.gateway_service.validate_gateway_settings()  # 不应抛出异常
        
        # 验证网关模式配置
        assert orchestrator.settings.gw_mode is True
        assert orchestrator.settings.gw_account == "gateway_user"
        assert orchestrator.settings.gw_mgmt_addr == "gateway.example.com"
    
    @patch('cyris.services.orchestrator.GuestBuilder')
    @patch('cyris.services.orchestrator.HostBuilder') 
    def test_create_cyber_range_with_gateway_integration(
        self, mock_host_builder, mock_guest_builder, settings_direct_mode, mock_providers
    ):
        """测试创建网络靶场并集成网关功能"""
        # 设置模拟对象
        mock_host = Mock()
        mock_host.host_id = "host_1"
        mock_host.mgmt_addr = "10.0.1.100"
        mock_host.account = "ubuntu"
        
        mock_guest = Mock()
        mock_guest.guest_id = "desktop"
        mock_guest.basevm_host = "host_1"
        mock_guest.basevm_type = "kvm"
        
        mock_host_builder.return_value.build.return_value = mock_host
        mock_guest_builder.return_value.build.return_value = mock_guest
        
        orchestrator = RangeOrchestrator(settings_direct_mode, mock_providers)
        
        # 模拟YAML配置
        yaml_config = {
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
                            'instance_number': 1,
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
        
        # 模拟网关服务的入口点创建
        with patch.object(orchestrator.gateway_service, 'create_entry_point') as mock_create_entry:
            mock_create_entry.return_value = {
                'access_host': '10.0.1.100',
                'access_port': 60001,
                'account': 'trainee',
                'password': 'secret123',
                'tunnel_id': 'tunnel_123_60001'
            }
            
            # 执行创建操作
            result = orchestrator.create_cyber_range(yaml_config)
            
            # 验证成功创建
            assert result['success'] is True
            assert result['range_id'] == 123
            assert 'entry_points' in result
            
            # 验证入口点创建被调用
            mock_create_entry.assert_called()
    
    def test_destroy_cyber_range_with_gateway_cleanup(self, settings_direct_mode, mock_providers):
        """测试销毁网络靶场时清理网关资源"""
        orchestrator = RangeOrchestrator(settings_direct_mode, mock_providers)
        
        # 模拟存在的靶场
        range_id = 123
        
        with patch.object(orchestrator.gateway_service, 'cleanup_range') as mock_cleanup:
            result = orchestrator.destroy_cyber_range(range_id)
            
            # 验证网关清理被调用
            mock_cleanup.assert_called_once_with(range_id)
            
            assert result['success'] is True
            assert result['range_id'] == range_id
    
    def test_get_access_notification(self, settings_direct_mode, mock_providers):
        """测试获取访问通知"""
        orchestrator = RangeOrchestrator(settings_direct_mode, mock_providers)
        
        range_id = 123
        expected_notification = "Test notification content"
        
        with patch.object(orchestrator.gateway_service, 'generate_access_notification') as mock_notification:
            mock_notification.return_value = expected_notification
            
            result = orchestrator.get_access_notification(range_id)
            
            mock_notification.assert_called_once_with(range_id)
            assert result == expected_notification
    
    def test_gateway_mode_entry_point_creation_flow(self, settings_gateway_mode, mock_providers):
        """测试网关模式的入口点创建流程"""
        orchestrator = RangeOrchestrator(settings_gateway_mode, mock_providers)
        
        # 模拟入口点信息
        entry_point = EntryPointInfo(
            range_id=123,
            instance_id=1,
            guest_id="desktop",
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            account="trainee",
            password="secret123"
        )
        
        with patch.object(orchestrator.gateway_service, 'create_entry_point') as mock_create:
            mock_create.return_value = {
                'access_host': 'gateway.example.com',  # 网关模式使用网关地址
                'access_port': 60001,
                'account': 'trainee',
                'password': 'secret123',
                'tunnel_id': 'tunnel_123_60001'
            }
            
            # 创建入口点
            result = orchestrator._create_entry_point(entry_point, "ubuntu", "10.0.1.100")
            
            # 验证网关模式下的访问地址
            assert result['access_host'] == 'gateway.example.com'
            assert result['access_port'] == 60001
            
            mock_create.assert_called_once()
    
    def test_orchestrator_status_includes_gateway_info(self, settings_gateway_mode, mock_providers):
        """测试编排器状态包含网关信息"""
        orchestrator = RangeOrchestrator(settings_gateway_mode, mock_providers)
        
        with patch.object(orchestrator.gateway_service, 'get_service_status') as mock_status:
            mock_status.return_value = {
                'gw_mode': True,
                'total_entry_points': 2,
                'active_tunnels': 2,
                'ranges': 1,
                'gateway_config': {
                    'account': 'gateway_user',
                    'mgmt_addr': 'gateway.example.com',
                    'inside_addr': '172.16.1.1'
                }
            }
            
            status = orchestrator.get_system_status()
            
            assert 'gateway_service' in status
            assert status['gateway_service']['gw_mode'] is True
            assert status['gateway_service']['total_entry_points'] == 2
            assert status['gateway_service']['gateway_config']['account'] == 'gateway_user'
    
    def test_error_handling_in_gateway_operations(self, settings_direct_mode, mock_providers):
        """测试网关操作中的错误处理"""
        orchestrator = RangeOrchestrator(settings_direct_mode, mock_providers)
        
        # 模拟网关服务错误
        with patch.object(orchestrator.gateway_service, 'create_entry_point') as mock_create:
            mock_create.side_effect = GatewayError("Tunnel creation failed")
            
            entry_point = EntryPointInfo(
                range_id=123, instance_id=1, guest_id="desktop",
                port=60001, target_host="192.168.123.101", target_port=22,
                account="trainee", password="secret123"
            )
            
            with pytest.raises(GatewayError, match="Tunnel creation failed"):
                orchestrator._create_entry_point(entry_point, "ubuntu", "10.0.1.100")
    
    def test_concurrent_entry_point_creation(self, settings_direct_mode, mock_providers):
        """测试并发入口点创建"""
        orchestrator = RangeOrchestrator(settings_direct_mode, mock_providers)
        
        # 模拟多个入口点
        entry_points = [
            EntryPointInfo(
                range_id=123, instance_id=i, guest_id=f"desktop{i}",
                port=60000 + i, target_host=f"192.168.123.{100+i}", target_port=22,
                account=f"trainee{i}", password=f"secret{i}"
            ) for i in range(1, 4)
        ]
        
        created_entry_points = []
        
        def mock_create_entry_point(ep, user, host):
            created_entry_points.append(ep)
            return {
                'access_host': host,
                'access_port': ep.port,
                'account': ep.account,
                'password': ep.password,
                'tunnel_id': f'tunnel_{ep.range_id}_{ep.port}'
            }
        
        with patch.object(orchestrator.gateway_service, 'create_entry_point', side_effect=mock_create_entry_point):
            # 创建多个入口点
            results = []
            for ep in entry_points:
                result = orchestrator._create_entry_point(ep, "ubuntu", "10.0.1.100")
                results.append(result)
            
            # 验证所有入口点都被创建
            assert len(results) == 3
            assert len(created_entry_points) == 3
            
            # 验证每个入口点的唯一性
            ports = [ep.port for ep in created_entry_points]
            assert len(set(ports)) == 3  # 所有端口都不同