"""
SSH隧道管理器 - 实现gw_mode功能的核心组件
支持直接模式和网关模式的SSH隧道创建和管理
"""
import logging
import subprocess
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from cyris.config.settings import CyRISSettings
from cyris.core.exceptions import TunnelError


logger = logging.getLogger(__name__)


@dataclass
class TunnelConfiguration:
    """SSH隧道配置"""
    range_id: int
    port: int
    target_host: str
    target_port: int
    local_user: str
    gw_mode: bool = False
    gw_account: Optional[str] = None
    gw_host: Optional[str] = None
    
    def __post_init__(self):
        """配置后验证"""
        if self.gw_mode and (not self.gw_account or not self.gw_host):
            raise ValueError(
                "Gateway mode requires gw_account and gw_host to be specified"
            )


@dataclass
class TunnelInfo:
    """隧道信息"""
    tunnel_id: str
    config: TunnelConfiguration
    created_at: datetime
    process_names: List[str]  # 隧道进程名称列表


class TunnelManager:
    """SSH隧道管理器"""
    
    def __init__(self, settings: CyRISSettings):
        """
        初始化隧道管理器
        
        Args:
            settings: CyRIS配置
        """
        self.settings = settings
        self.active_tunnels: Dict[str, TunnelInfo] = {}
        logger.info(f"TunnelManager initialized, gw_mode={settings.gw_mode}")
    
    def create_tunnel(self, config: TunnelConfiguration) -> str:
        """
        创建SSH隧道
        
        Args:
            config: 隧道配置
            
        Returns:
            str: 隧道ID
            
        Raises:
            TunnelError: 隧道创建失败
        """
        tunnel_id = f"tunnel_{config.range_id}_{config.port}_{uuid.uuid4().hex[:8]}"
        process_names = []
        
        try:
            if config.gw_mode:
                # 网关模式：创建两级隧道
                process_names = self._create_gateway_tunnel(config)
            else:
                # 直接模式：创建直接隧道
                process_names = self._create_direct_tunnel(config)
            
            # 记录隧道信息
            tunnel_info = TunnelInfo(
                tunnel_id=tunnel_id,
                config=config,
                created_at=datetime.now(),
                process_names=process_names
            )
            self.active_tunnels[tunnel_id] = tunnel_info
            
            logger.info(f"Tunnel created successfully: {tunnel_id}")
            return tunnel_id
            
        except Exception as e:
            logger.error(f"Failed to create tunnel: {e}")
            # 清理可能部分创建的隧道
            for process_name in process_names:
                self._kill_process_by_name(process_name)
            raise TunnelError(f"Failed to create tunnel: {e}")
    
    def _create_direct_tunnel(self, config: TunnelConfiguration) -> List[str]:
        """
        创建直接模式隧道
        
        Args:
            config: 隧道配置
            
        Returns:
            List[str]: 创建的进程名称列表
        """
        process_name = f"ct{config.range_id}_{config.port}"
        
        command = [
            'bash', '-c',
            f"exec -a {process_name} ssh -o UserKnownHostsFile=/dev/null "
            f"-o StrictHostKeyChecking=no -f -L 0.0.0.0:{config.port}:"
            f"{config.target_host}:{config.target_port} {config.local_user}@localhost -N"
        ]
        
        logger.debug(f"Executing direct tunnel command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise TunnelError(
                f"Failed to create direct tunnel: {result.stderr}"
            )
        
        return [process_name]
    
    def _create_gateway_tunnel(self, config: TunnelConfiguration) -> List[str]:
        """
        创建网关模式隧道
        
        Args:
            config: 隧道配置
            
        Returns:
            List[str]: 创建的进程名称列表
        """
        process_names = []
        gateway_process = f"ct{config.range_id}_{config.port}_gw"
        local_process = f"ct{config.range_id}_{config.port}"
        
        # 1. 在网关服务器上创建隧道
        gateway_command = [
            'ssh',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            f'{config.gw_account}@{config.gw_host}',
            '-f',
            f"bash -c 'exec -a {gateway_process} ssh -o UserKnownHostsFile=/dev/null "
            f"-o StrictHostKeyChecking=no -f -L 0.0.0.0:{config.port}:localhost:{config.port} "
            f"{config.gw_account}@localhost -N'"
        ]
        
        logger.debug(f"Executing gateway tunnel command: {' '.join(gateway_command)}")
        result = subprocess.run(gateway_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise TunnelError(
                f"Failed to create gateway tunnel: {result.stderr}"
            )
        
        process_names.append(gateway_process)
        
        # 2. 在本地主机上创建隧道
        local_command = [
            'bash', '-c',
            f"exec -a {local_process} ssh -o UserKnownHostsFile=/dev/null "
            f"-o StrictHostKeyChecking=no -f -L 0.0.0.0:{config.port}:"
            f"{config.target_host}:{config.target_port} {config.local_user}@localhost -N"
        ]
        
        logger.debug(f"Executing local tunnel command: {' '.join(local_command)}")
        result = subprocess.run(local_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            # 清理网关隧道
            self._kill_process_on_gateway(gateway_process, config.gw_account, config.gw_host)
            raise TunnelError(
                f"Failed to create local tunnel: {result.stderr}"
            )
        
        process_names.append(local_process)
        return process_names
    
    def destroy_tunnel(self, tunnel_id: str) -> None:
        """
        销毁SSH隧道
        
        Args:
            tunnel_id: 隧道ID
            
        Raises:
            TunnelError: 隧道不存在或销毁失败
        """
        if tunnel_id not in self.active_tunnels:
            raise TunnelError(f"Tunnel not found: {tunnel_id}")
        
        tunnel_info = self.active_tunnels[tunnel_id]
        
        try:
            if tunnel_info.config.gw_mode:
                self._destroy_gateway_tunnel(tunnel_info)
            else:
                self._destroy_direct_tunnel(tunnel_info)
            
            # 从活跃隧道列表中移除
            del self.active_tunnels[tunnel_id]
            logger.info(f"Tunnel destroyed successfully: {tunnel_id}")
            
        except Exception as e:
            logger.error(f"Failed to destroy tunnel {tunnel_id}: {e}")
            raise TunnelError(f"Failed to destroy tunnel: {e}")
    
    def _destroy_direct_tunnel(self, tunnel_info: TunnelInfo) -> None:
        """
        销毁直接模式隧道
        
        Args:
            tunnel_info: 隧道信息
        """
        for process_name in tunnel_info.process_names:
            self._kill_process_by_name(process_name)
    
    def _destroy_gateway_tunnel(self, tunnel_info: TunnelInfo) -> None:
        """
        销毁网关模式隧道
        
        Args:
            tunnel_info: 隧道信息
        """
        config = tunnel_info.config
        
        for process_name in tunnel_info.process_names:
            if process_name.endswith('_gw'):
                # 销毁网关上的隧道
                self._kill_process_on_gateway(
                    process_name, config.gw_account, config.gw_host
                )
            else:
                # 销毁本地隧道
                self._kill_process_by_name(process_name)
    
    def _kill_process_by_name(self, process_name: str) -> None:
        """
        根据进程名杀死进程
        
        Args:
            process_name: 进程名
        """
        command = ['pkill', '-f', process_name]
        logger.debug(f"Killing local process: {process_name}")
        subprocess.run(command, capture_output=True, text=True)
    
    def _kill_process_on_gateway(self, process_name: str, gw_account: str, gw_host: str) -> None:
        """
        在网关服务器上杀死进程
        
        Args:
            process_name: 进程名
            gw_account: 网关账户
            gw_host: 网关主机
        """
        command = [
            'ssh',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            f'{gw_account}@{gw_host}',
            f'pkill -f {process_name}'
        ]
        
        logger.debug(f"Killing gateway process: {process_name}")
        subprocess.run(command, capture_output=True, text=True)
    
    def list_active_tunnels(self) -> List[Dict[str, Any]]:
        """
        列出所有活跃隧道
        
        Returns:
            List[Dict]: 隧道信息列表
        """
        tunnels = []
        
        for tunnel_id, tunnel_info in self.active_tunnels.items():
            config = tunnel_info.config
            tunnels.append({
                'tunnel_id': tunnel_id,
                'range_id': config.range_id,
                'port': config.port,
                'target_host': config.target_host,
                'target_port': config.target_port,
                'gw_mode': config.gw_mode,
                'created_at': tunnel_info.created_at,
                'process_names': tunnel_info.process_names
            })
        
        return tunnels
    
    def get_tunnel_info(self, tunnel_id: str) -> Optional[TunnelInfo]:
        """
        获取隧道信息
        
        Args:
            tunnel_id: 隧道ID
            
        Returns:
            TunnelInfo: 隧道信息，如果不存在返回None
        """
        return self.active_tunnels.get(tunnel_id)
    
    def cleanup_all_tunnels(self) -> None:
        """清理所有隧道"""
        tunnel_ids = list(self.active_tunnels.keys())
        
        for tunnel_id in tunnel_ids:
            try:
                self.destroy_tunnel(tunnel_id)
            except Exception as e:
                logger.error(f"Failed to cleanup tunnel {tunnel_id}: {e}")
        
        logger.info(f"Cleaned up {len(tunnel_ids)} tunnels")