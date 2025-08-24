"""
测试SSH隧道管理器 - TDD实现gw_mode功能
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, call
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.infrastructure.network.tunnel_manager import TunnelManager, TunnelConfiguration
from cyris.config.settings import CyRISSettings
from cyris.core.exceptions import TunnelError


class TestTunnelConfiguration:
    """测试隧道配置"""
    
    def test_direct_mode_tunnel_config(self):
        """测试直接模式隧道配置"""
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=False
        )
        
        assert config.range_id == 123
        assert config.port == 60001
        assert config.target_host == "192.168.123.101"
        assert config.target_port == 22
        assert config.local_user == "ubuntu"
        assert config.gw_mode is False
        assert config.gw_account is None
        assert config.gw_host is None
    
    def test_gateway_mode_tunnel_config(self):
        """测试网关模式隧道配置"""
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=True,
            gw_account="gateway_user",
            gw_host="gateway.example.com"
        )
        
        assert config.gw_mode is True
        assert config.gw_account == "gateway_user"
        assert config.gw_host == "gateway.example.com"
    
    def test_gateway_mode_validation(self):
        """测试网关模式配置验证"""
        with pytest.raises(ValueError, match="Gateway mode requires gw_account"):
            TunnelConfiguration(
                range_id=123,
                port=60001,
                target_host="192.168.123.101",
                target_port=22,
                local_user="ubuntu",
                gw_mode=True
                # 缺少gw_account
            )


class TestTunnelManager:
    """测试隧道管理器"""
    
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
    
    def test_tunnel_manager_initialization(self, settings_direct_mode):
        """测试隧道管理器初始化"""
        manager = TunnelManager(settings_direct_mode)
        
        assert manager.settings == settings_direct_mode
        assert len(manager.active_tunnels) == 0
    
    @patch('subprocess.run')
    def test_create_direct_mode_tunnel(self, mock_subprocess, settings_direct_mode):
        """测试创建直接模式隧道"""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        manager = TunnelManager(settings_direct_mode)
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=False
        )
        
        tunnel_id = manager.create_tunnel(config)
        
        # 验证隧道创建
        assert tunnel_id in manager.active_tunnels
        
        # 验证执行的命令
        expected_command = [
            'bash', '-c',
            "exec -a ct123_60001 ssh -o UserKnownHostsFile=/dev/null "
            "-o StrictHostKeyChecking=no -f -L 0.0.0.0:60001:192.168.123.101:22 "
            "ubuntu@localhost -N"
        ]
        mock_subprocess.assert_called_once_with(expected_command, capture_output=True, text=True)
    
    @patch('subprocess.run')
    def test_create_gateway_mode_tunnel(self, mock_subprocess, settings_gateway_mode):
        """测试创建网关模式隧道"""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        manager = TunnelManager(settings_gateway_mode)
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=True,
            gw_account="gateway_user",
            gw_host="gateway.example.com"
        )
        
        tunnel_id = manager.create_tunnel(config)
        
        # 验证隧道创建
        assert tunnel_id in manager.active_tunnels
        
        # 验证执行了两个命令（网关隧道 + 本地隧道）
        assert mock_subprocess.call_count == 2
        
        # 验证网关隧道命令
        gateway_command = [
            'ssh', '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            'gateway_user@gateway.example.com', '-f',
            'bash -c \'exec -a ct123_60001 ssh -o UserKnownHostsFile=/dev/null '
            '-o StrictHostKeyChecking=no -f -L 0.0.0.0:60001:localhost:60001 '
            'gateway_user@localhost -N\''
        ]
        
        # 验证本地隧道命令
        local_command = [
            'bash', '-c',
            "exec -a ct123_60001 ssh -o UserKnownHostsFile=/dev/null "
            "-o StrictHostKeyChecking=no -f -L 0.0.0.0:60001:192.168.123.101:22 "
            "ubuntu@localhost -N"
        ]
        
        calls = mock_subprocess.call_args_list
        assert len(calls) == 2
    
    @patch('subprocess.run')
    def test_tunnel_creation_failure(self, mock_subprocess, settings_direct_mode):
        """测试隧道创建失败"""
        mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Connection failed")
        
        manager = TunnelManager(settings_direct_mode)
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=False
        )
        
        with pytest.raises(TunnelError, match="Failed to create tunnel"):
            manager.create_tunnel(config)
    
    @patch('subprocess.run')
    def test_destroy_tunnel(self, mock_subprocess, settings_direct_mode):
        """测试销毁隧道"""
        # 模拟创建隧道
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        manager = TunnelManager(settings_direct_mode)
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=False
        )
        
        tunnel_id = manager.create_tunnel(config)
        assert tunnel_id in manager.active_tunnels
        
        # 销毁隧道
        manager.destroy_tunnel(tunnel_id)
        
        # 验证隧道已移除
        assert tunnel_id not in manager.active_tunnels
        
        # 验证执行了pkill命令
        destroy_calls = [call for call in mock_subprocess.call_args_list 
                        if 'pkill' in str(call)]
        assert len(destroy_calls) > 0
    
    @patch('subprocess.run')
    def test_destroy_gateway_mode_tunnel(self, mock_subprocess, settings_gateway_mode):
        """测试销毁网关模式隧道"""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        manager = TunnelManager(settings_gateway_mode)
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=True,
            gw_account="gateway_user",
            gw_host="gateway.example.com"
        )
        
        tunnel_id = manager.create_tunnel(config)
        manager.destroy_tunnel(tunnel_id)
        
        # 验证隧道已移除
        assert tunnel_id not in manager.active_tunnels
        
        # 验证执行了网关和本地的pkill命令
        destroy_calls = [call for call in mock_subprocess.call_args_list 
                        if 'pkill' in str(call)]
        assert len(destroy_calls) >= 2  # 至少有网关和本地两个销毁命令
    
    def test_list_active_tunnels(self, settings_direct_mode):
        """测试列出活跃隧道"""
        manager = TunnelManager(settings_direct_mode)
        
        # 初始状态无隧道
        assert manager.list_active_tunnels() == []
        
        # 添加模拟隧道
        config = TunnelConfiguration(
            range_id=123,
            port=60001,
            target_host="192.168.123.101",
            target_port=22,
            local_user="ubuntu",
            gw_mode=False
        )
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
            tunnel_id = manager.create_tunnel(config)
        
        # 验证隧道在列表中
        active_tunnels = manager.list_active_tunnels()
        assert len(active_tunnels) == 1
        assert active_tunnels[0]['tunnel_id'] == tunnel_id
        assert active_tunnels[0]['range_id'] == 123
        assert active_tunnels[0]['port'] == 60001