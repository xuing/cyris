"""
网关模式服务 - 管理gw_mode功能的入口点和访问控制
支持直接模式和网关模式的访问管理
"""
import logging
import string
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

from cyris.config.settings import CyRISSettings
from cyris.infrastructure.network.tunnel_manager import TunnelManager, TunnelConfiguration
from cyris.core.exceptions import GatewayError


logger = logging.getLogger(__name__)


@dataclass
class EntryPointInfo:
    """入口点信息"""
    range_id: int
    instance_id: int
    guest_id: str
    port: int
    target_host: str
    target_port: int
    account: str
    password: str
    tunnel_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class GatewayService:
    """网关模式服务"""
    
    def __init__(self, settings: CyRISSettings, tunnel_manager: TunnelManager):
        """
        初始化网关服务
        
        Args:
            settings: CyRIS配置
            tunnel_manager: 隧道管理器
        """
        self.settings = settings
        self.tunnel_manager = tunnel_manager
        self.entry_points: List[EntryPointInfo] = []
        self.access_info_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"GatewayService initialized, gw_mode={settings.gw_mode}")
    
    def validate_gateway_settings(self) -> None:
        """
        验证网关配置
        
        Raises:
            GatewayError: 网关配置无效
        """
        if not self.settings.gw_mode:
            # 直接模式不需要额外配置
            return
        
        # 网关模式需要的配置
        missing_configs = []
        
        if not self.settings.gw_account:
            missing_configs.append("gw_account")
        
        if not self.settings.gw_mgmt_addr:
            missing_configs.append("gw_mgmt_addr")
        
        if not self.settings.gw_inside_addr:
            missing_configs.append("gw_inside_addr")
        
        if missing_configs:
            raise GatewayError(
                f"Gateway mode requires the following configurations: {', '.join(missing_configs)}"
            )
        
        logger.debug("Gateway settings validation passed")
    
    def create_entry_point(
        self, 
        entry_point: EntryPointInfo, 
        local_user: str, 
        host_address: str
    ) -> Dict[str, Any]:
        """
        创建入口点
        
        Args:
            entry_point: 入口点信息
            local_user: 本地用户账户
            host_address: 主机地址
            
        Returns:
            Dict: 访问信息
            
        Raises:
            GatewayError: 创建失败
        """
        try:
            # 验证网关配置
            self.validate_gateway_settings()
            
            # 创建隧道配置
            tunnel_config = TunnelConfiguration(
                range_id=entry_point.range_id,
                port=entry_point.port,
                target_host=entry_point.target_host,
                target_port=entry_point.target_port,
                local_user=local_user,
                gw_mode=self.settings.gw_mode,
                gw_account=self.settings.gw_account,
                gw_host=self.settings.gw_mgmt_addr
            )
            
            # 创建隧道
            tunnel_id = self.tunnel_manager.create_tunnel(tunnel_config)
            entry_point.tunnel_id = tunnel_id
            
            # 记录入口点
            self.entry_points.append(entry_point)
            
            # 生成访问信息
            access_info = self._generate_access_info(entry_point, host_address)
            
            # 缓存访问信息
            cache_key = f"{entry_point.range_id}_{entry_point.instance_id}"
            self.access_info_cache[cache_key] = access_info
            
            logger.info(
                f"Entry point created: range={entry_point.range_id}, "
                f"instance={entry_point.instance_id}, port={entry_point.port}"
            )
            
            return access_info
            
        except Exception as e:
            logger.error(f"Failed to create entry point: {e}")
            raise GatewayError(f"Failed to create entry point: {e}")
    
    def _generate_access_info(self, entry_point: EntryPointInfo, host_address: str) -> Dict[str, Any]:
        """
        生成访问信息
        
        Args:
            entry_point: 入口点信息
            host_address: 主机地址
            
        Returns:
            Dict: 访问信息
        """
        if self.settings.gw_mode:
            # 网关模式：通过网关访问
            access_host = self.settings.gw_mgmt_addr
        else:
            # 直接模式：直接访问主机
            access_host = host_address
        
        return {
            'access_host': access_host,
            'access_port': entry_point.port,
            'account': entry_point.account,
            'password': entry_point.password,
            'tunnel_id': entry_point.tunnel_id,
            'range_id': entry_point.range_id,
            'instance_id': entry_point.instance_id,
            'guest_id': entry_point.guest_id
        }
    
    def destroy_entry_point(self, range_id: int, instance_id: int) -> None:
        """
        销毁入口点
        
        Args:
            range_id: 靶场ID
            instance_id: 实例ID
            
        Raises:
            GatewayError: 销毁失败
        """
        try:
            # 查找入口点
            entry_point = None
            for ep in self.entry_points:
                if ep.range_id == range_id and ep.instance_id == instance_id:
                    entry_point = ep
                    break
            
            if not entry_point:
                raise GatewayError(
                    f"Entry point not found: range_id={range_id}, instance_id={instance_id}"
                )
            
            # 销毁隧道
            if entry_point.tunnel_id:
                self.tunnel_manager.destroy_tunnel(entry_point.tunnel_id)
            
            # 从列表中移除
            self.entry_points.remove(entry_point)
            
            # 清除缓存
            cache_key = f"{range_id}_{instance_id}"
            self.access_info_cache.pop(cache_key, None)
            
            logger.info(f"Entry point destroyed: range={range_id}, instance={instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to destroy entry point: {e}")
            raise GatewayError(f"Failed to destroy entry point: {e}")
    
    def get_entry_points_for_range(self, range_id: int) -> List[EntryPointInfo]:
        """
        获取指定靶场的入口点列表
        
        Args:
            range_id: 靶场ID
            
        Returns:
            List[EntryPointInfo]: 入口点列表
        """
        return [ep for ep in self.entry_points if ep.range_id == range_id]
    
    def generate_access_notification(self, range_id: int) -> str:
        """
        生成访问通知
        
        Args:
            range_id: 靶场ID
            
        Returns:
            str: 访问通知内容
        """
        entry_points = self.get_entry_points_for_range(range_id)
        
        if not entry_points:
            return f"No entry points available for range {range_id}"
        
        notification_lines = [
            "=" * 60,
            f"Cyber Range Access Information",
            f"Range ID: {range_id}",
            f"Total Entry Points: {len(entry_points)}",
            "=" * 60,
            ""
        ]
        
        for i, ep in enumerate(entry_points, 1):
            cache_key = f"{ep.range_id}_{ep.instance_id}"
            access_info = self.access_info_cache.get(cache_key)
            
            if access_info:
                notification_lines.extend([
                    f"Entry Point #{i}:",
                    f"  Guest: {ep.guest_id}",
                    f"  Login: ssh {access_info['account']}@{access_info['access_host']} -p {access_info['access_port']}",
                    f"  Password: {access_info['password']}",
                    ""
                ])
        
        notification_lines.extend([
            "=" * 60,
            f"Mode: {'Gateway' if self.settings.gw_mode else 'Direct'}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60
        ])
        
        return "\n".join(notification_lines)
    
    def generate_random_credentials(self, length: int = 12) -> str:
        """
        生成随机密码
        
        Args:
            length: 密码长度
            
        Returns:
            str: 随机密码
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def get_available_port(self, start_port: int = 60000, end_port: int = 65000) -> int:
        """
        获取可用端口
        
        Args:
            start_port: 起始端口
            end_port: 结束端口
            
        Returns:
            int: 可用端口
        """
        used_ports = {ep.port for ep in self.entry_points}
        
        for port in range(start_port, end_port + 1):
            if port not in used_ports:
                return port
        
        raise GatewayError(f"No available ports in range {start_port}-{end_port}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态
        
        Returns:
            Dict: 服务状态信息
        """
        return {
            'gw_mode': self.settings.gw_mode,
            'total_entry_points': len(self.entry_points),
            'active_tunnels': len(self.tunnel_manager.active_tunnels),
            'ranges': len(set(ep.range_id for ep in self.entry_points)),
            'gateway_config': {
                'account': self.settings.gw_account,
                'mgmt_addr': self.settings.gw_mgmt_addr,
                'inside_addr': self.settings.gw_inside_addr
            } if self.settings.gw_mode else None
        }
    
    def cleanup_range(self, range_id: int) -> None:
        """
        清理指定靶场的所有入口点
        
        Args:
            range_id: 靶场ID
        """
        entry_points = self.get_entry_points_for_range(range_id)
        
        for ep in entry_points:
            try:
                self.destroy_entry_point(ep.range_id, ep.instance_id)
            except Exception as e:
                logger.error(f"Failed to cleanup entry point {ep.range_id}_{ep.instance_id}: {e}")
        
        logger.info(f"Cleaned up {len(entry_points)} entry points for range {range_id}")
    
    def cleanup_all(self) -> None:
        """清理所有入口点和隧道"""
        entry_points_count = len(self.entry_points)
        
        # 清理所有隧道
        self.tunnel_manager.cleanup_all_tunnels()
        
        # 清理入口点列表和缓存
        self.entry_points.clear()
        self.access_info_cache.clear()
        
        logger.info(f"Cleaned up all {entry_points_count} entry points and tunnels")