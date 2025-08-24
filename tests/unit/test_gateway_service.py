"""
测试网关模式服务 - TDD实现
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.services.gateway_service import GatewayService, EntryPointInfo
from cyris.config.settings import CyRISSettings
from cyris.domain.entities.host import Host
from cyris.domain.entities.guest import Guest
from cyris.core.exceptions import GatewayError


class TestEntryPointInfo:
    """测试入口点信息"""
    
    def test_entry_point_info_creation(self):
        """测试入口点信息创建"""
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
        
        assert entry_point.range_id == 123
        assert entry_point.instance_id == 1
        assert entry_point.guest_id == "desktop"
        assert entry_point.port == 60001
        assert entry_point.target_host == "192.168.123.101"
        assert entry_point.target_port == 22
        assert entry_point.account == "trainee"
        assert entry_point.password == "secret123"


class TestGatewayService:
    """测试网关模式服务"""
    
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
    def mock_tunnel_manager(self):
        """模拟隧道管理器"""
        return Mock()
    
    @pytest.fixture
    def sample_hosts(self):
        """示例主机列表"""
        return [
            Host(host_id="host_1", mgmt_addr="10.0.1.100", account="ubuntu")
        ]
    
    @pytest.fixture
    def sample_guests(self):
        """示例虚拟机列表"""
        return [
            Guest(guest_id="desktop", basevm_host="host_1", basevm_type="kvm")
        ]
    
    def test_gateway_service_initialization_direct_mode(self, settings_direct_mode, mock_tunnel_manager):
        """测试直接模式网关服务初始化"""
        service = GatewayService(settings_direct_mode, mock_tunnel_manager)
        
        assert service.settings == settings_direct_mode
        assert service.tunnel_manager == mock_tunnel_manager
        assert service.settings.gw_mode is False
        assert len(service.entry_points) == 0
    
    def test_gateway_service_initialization_gateway_mode(self, settings_gateway_mode, mock_tunnel_manager):
        """测试网关模式网关服务初始化"""
        service = GatewayService(settings_gateway_mode, mock_tunnel_manager)
        
        assert service.settings == settings_gateway_mode
        assert service.settings.gw_mode is True
        assert service.settings.gw_account == "gateway_user"
        assert service.settings.gw_mgmt_addr == "gateway.example.com"
    
    def test_validate_gateway_settings_direct_mode(self, settings_direct_mode, mock_tunnel_manager):
        """测试直接模式设置验证"""
        service = GatewayService(settings_direct_mode, mock_tunnel_manager)
        # 直接模式不需要额外验证
        service.validate_gateway_settings()  # 应该不抛出异常
    
    def test_validate_gateway_settings_gateway_mode_valid(self, settings_gateway_mode, mock_tunnel_manager):
        """测试有效网关模式设置验证"""
        service = GatewayService(settings_gateway_mode, mock_tunnel_manager)
        service.validate_gateway_settings()  # 应该不抛出异常
    
    def test_validate_gateway_settings_gateway_mode_invalid(self, mock_tunnel_manager):
        """测试无效网关模式设置验证"""
        invalid_settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            gw_mode=True
            # 缺少gw_account等必要配置
        )
        
        service = GatewayService(invalid_settings, mock_tunnel_manager)
        
        with pytest.raises(GatewayError, match="Gateway mode requires"):
            service.validate_gateway_settings()
    
    def test_create_entry_point_direct_mode(self, settings_direct_mode, mock_tunnel_manager):
        """测试直接模式创建入口点"""
        service = GatewayService(settings_direct_mode, mock_tunnel_manager)
        mock_tunnel_manager.create_tunnel.return_value = "tunnel_123_60001"
        
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
        
        result = service.create_entry_point(entry_point, "ubuntu", "10.0.1.100")
        
        # 验证返回的访问信息
        assert result['access_host'] == "10.0.1.100"  # 直接模式使用主机地址
        assert result['access_port'] == 60001
        assert result['account'] == "trainee"
        assert result['password'] == "secret123"
        assert result['tunnel_id'] == "tunnel_123_60001"
        
        # 验证隧道管理器被调用
        mock_tunnel_manager.create_tunnel.assert_called_once()
        
        # 验证入口点被记录
        assert len(service.entry_points) == 1
        assert service.entry_points[0] == entry_point
    
    def test_create_entry_point_gateway_mode(self, settings_gateway_mode, mock_tunnel_manager):
        """测试网关模式创建入口点"""
        service = GatewayService(settings_gateway_mode, mock_tunnel_manager)
        mock_tunnel_manager.create_tunnel.return_value = "tunnel_123_60001"
        
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
        
        result = service.create_entry_point(entry_point, "ubuntu", "10.0.1.100")
        
        # 验证返回的访问信息
        assert result['access_host'] == "gateway.example.com"  # 网关模式使用网关地址
        assert result['access_port'] == 60001
        assert result['account'] == "trainee"
        assert result['password'] == "secret123"
        assert result['tunnel_id'] == "tunnel_123_60001"
        
        # 验证隧道管理器被调用
        mock_tunnel_manager.create_tunnel.assert_called_once()
    
    def test_destroy_entry_point(self, settings_direct_mode, mock_tunnel_manager):
        """测试销毁入口点"""
        service = GatewayService(settings_direct_mode, mock_tunnel_manager)
        mock_tunnel_manager.create_tunnel.return_value = "tunnel_123_60001"
        
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
        
        # 创建入口点
        service.create_entry_point(entry_point, "ubuntu", "10.0.1.100")
        assert len(service.entry_points) == 1
        
        # 销毁入口点
        service.destroy_entry_point(123, 1)
        
        # 验证入口点被移除
        assert len(service.entry_points) == 0
        
        # 验证隧道被销毁
        mock_tunnel_manager.destroy_tunnel.assert_called_once_with("tunnel_123_60001")
    
    def test_get_entry_points_for_range(self, settings_direct_mode, mock_tunnel_manager):
        """测试获取靶场入口点列表"""
        service = GatewayService(settings_direct_mode, mock_tunnel_manager)
        mock_tunnel_manager.create_tunnel.return_value = "tunnel_123_60001"
        
        # 创建多个入口点
        entry_point1 = EntryPointInfo(
            range_id=123, instance_id=1, guest_id="desktop",
            port=60001, target_host="192.168.123.101", target_port=22,
            account="trainee1", password="secret1"
        )
        entry_point2 = EntryPointInfo(
            range_id=123, instance_id=2, guest_id="server",
            port=60002, target_host="192.168.123.102", target_port=22,
            account="trainee2", password="secret2"
        )
        entry_point3 = EntryPointInfo(
            range_id=456, instance_id=1, guest_id="desktop",
            port=60003, target_host="192.168.456.101", target_port=22,
            account="trainee3", password="secret3"
        )
        
        service.create_entry_point(entry_point1, "ubuntu", "10.0.1.100")
        service.create_entry_point(entry_point2, "ubuntu", "10.0.1.100")
        service.create_entry_point(entry_point3, "ubuntu", "10.0.1.100")
        
        # 获取range 123的入口点
        range_123_entries = service.get_entry_points_for_range(123)
        assert len(range_123_entries) == 2
        
        range_ids = [ep.range_id for ep in range_123_entries]
        assert all(rid == 123 for rid in range_ids)
    
    def test_generate_access_notification_direct_mode(self, settings_direct_mode, mock_tunnel_manager):
        """测试生成直接模式访问通知"""
        service = GatewayService(settings_direct_mode, mock_tunnel_manager)
        mock_tunnel_manager.create_tunnel.return_value = "tunnel_123_60001"
        
        entry_point = EntryPointInfo(
            range_id=123, instance_id=1, guest_id="desktop",
            port=60001, target_host="192.168.123.101", target_port=22,
            account="trainee", password="secret123"
        )
        
        access_info = service.create_entry_point(entry_point, "ubuntu", "10.0.1.100")
        notification = service.generate_access_notification(123)
        
        assert "Range ID: 123" in notification
        assert "ssh trainee@10.0.1.100 -p 60001" in notification
        assert "Password: secret123" in notification
    
    def test_generate_access_notification_gateway_mode(self, settings_gateway_mode, mock_tunnel_manager):
        """测试生成网关模式访问通知"""
        service = GatewayService(settings_gateway_mode, mock_tunnel_manager)
        mock_tunnel_manager.create_tunnel.return_value = "tunnel_123_60001"
        
        entry_point = EntryPointInfo(
            range_id=123, instance_id=1, guest_id="desktop",
            port=60001, target_host="192.168.123.101", target_port=22,
            account="trainee", password="secret123"
        )
        
        access_info = service.create_entry_point(entry_point, "ubuntu", "10.0.1.100")
        notification = service.generate_access_notification(123)
        
        assert "Range ID: 123" in notification
        assert "ssh trainee@gateway.example.com -p 60001" in notification  # 使用网关地址
        assert "Password: secret123" in notification