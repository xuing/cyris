"""
SSH Tunnel Manager - Core component implementing gw_mode functionality
Supports creating and managing SSH tunnels in both direct and gateway modes
"""
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import subprocess
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from cyris.config.settings import CyRISSettings
from cyris.core.exceptions import TunnelError


logger = get_logger(__name__, "tunnel_manager")


@dataclass
class TunnelConfiguration:
    """SSH tunnel configuration"""
    range_id: int
    port: int
    target_host: str
    target_port: int
    local_user: str
    gw_mode: bool = False
    gw_account: Optional[str] = None
    gw_host: Optional[str] = None
    
    def __post_init__(self):
        """Post-configuration validation"""
        if self.gw_mode and (not self.gw_account or not self.gw_host):
            raise ValueError(
                "Gateway mode requires gw_account and gw_host to be specified"
            )


@dataclass
class TunnelInfo:
    """Tunnel information"""
    tunnel_id: str
    config: TunnelConfiguration
    created_at: datetime
    process_names: List[str]  # List of tunnel process names


class TunnelManager:
    """SSH tunnel manager"""
    
    def __init__(self, settings: CyRISSettings):
        """
        Initialize tunnel manager
        
        Args:
            settings: CyRIS configuration
        """
        self.settings = settings
        self.active_tunnels: Dict[str, TunnelInfo] = {}
        logger.info(f"TunnelManager initialized, gw_mode={settings.gw_mode}")
    
    def create_tunnel(self, config: TunnelConfiguration) -> str:
        """
        Create SSH tunnel
        
        Args:
            config: Tunnel configuration
            
        Returns:
            str: Tunnel ID
            
        Raises:
            TunnelError: Tunnel creation failed
        """
        tunnel_id = f"tunnel_{config.range_id}_{config.port}_{uuid.uuid4().hex[:8]}"
        process_names = []
        
        try:
            if config.gw_mode:
                # Gateway mode: create two-level tunnel
                process_names = self._create_gateway_tunnel(config)
            else:
                # Direct mode: create direct tunnel
                process_names = self._create_direct_tunnel(config)
            
            # Record tunnel information
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
            # Clean up potentially partially created tunnel
            for process_name in process_names:
                self._kill_process_by_name(process_name)
            raise TunnelError(f"Failed to create tunnel: {e}")
    
    def _create_direct_tunnel(self, config: TunnelConfiguration) -> List[str]:
        """
        Create direct mode tunnel
        
        Args:
            config: Tunnel configuration
            
        Returns:
            List[str]: List of created process names
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
        Create gateway mode tunnel
        
        Args:
            config: Tunnel configuration
            
        Returns:
            List[str]: List of created process names
        """
        process_names = []
        gateway_process = f"ct{config.range_id}_{config.port}_gw"
        local_process = f"ct{config.range_id}_{config.port}"
        
        # 1. Create tunnel on gateway server
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
        
        # 2. Create tunnel on local host
        local_command = [
            'bash', '-c',
            f"exec -a {local_process} ssh -o UserKnownHostsFile=/dev/null "
            f"-o StrictHostKeyChecking=no -f -L 0.0.0.0:{config.port}:"
            f"{config.target_host}:{config.target_port} {config.local_user}@localhost -N"
        ]
        
        logger.debug(f"Executing local tunnel command: {' '.join(local_command)}")
        result = subprocess.run(local_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Clean up gateway tunnel
            self._kill_process_on_gateway(gateway_process, config.gw_account, config.gw_host)
            raise TunnelError(
                f"Failed to create local tunnel: {result.stderr}"
            )
        
        process_names.append(local_process)
        return process_names
    
    def destroy_tunnel(self, tunnel_id: str) -> None:
        """
        Destroy SSH tunnel
        
        Args:
            tunnel_id: Tunnel ID
            
        Raises:
            TunnelError: Tunnel not found or destruction failed
        """
        if tunnel_id not in self.active_tunnels:
            raise TunnelError(f"Tunnel not found: {tunnel_id}")
        
        tunnel_info = self.active_tunnels[tunnel_id]
        
        try:
            if tunnel_info.config.gw_mode:
                self._destroy_gateway_tunnel(tunnel_info)
            else:
                self._destroy_direct_tunnel(tunnel_info)
            
            # Remove from active tunnel list
            del self.active_tunnels[tunnel_id]
            logger.info(f"Tunnel destroyed successfully: {tunnel_id}")
            
        except Exception as e:
            logger.error(f"Failed to destroy tunnel {tunnel_id}: {e}")
            raise TunnelError(f"Failed to destroy tunnel: {e}")
    
    def _destroy_direct_tunnel(self, tunnel_info: TunnelInfo) -> None:
        """
        Destroy direct mode tunnel
        
        Args:
            tunnel_info: Tunnel information
        """
        for process_name in tunnel_info.process_names:
            self._kill_process_by_name(process_name)
    
    def _destroy_gateway_tunnel(self, tunnel_info: TunnelInfo) -> None:
        """
        Destroy gateway mode tunnel
        
        Args:
            tunnel_info: Tunnel information
        """
        config = tunnel_info.config
        
        for process_name in tunnel_info.process_names:
            if process_name.endswith('_gw'):
                # Destroy tunnel on gateway
                self._kill_process_on_gateway(
                    process_name, config.gw_account, config.gw_host
                )
            else:
                # Destroy local tunnel
                self._kill_process_by_name(process_name)
    
    def _kill_process_by_name(self, process_name: str) -> None:
        """
        Kill process by process name
        
        Args:
            process_name: Process name
        """
        command = ['pkill', '-f', process_name]
        logger.debug(f"Killing local process: {process_name}")
        subprocess.run(command, capture_output=True, text=True)
    
    def _kill_process_on_gateway(self, process_name: str, gw_account: str, gw_host: str) -> None:
        """
        Kill process on gateway server
        
        Args:
            process_name: Process name
            gw_account: Gateway account
            gw_host: Gateway host
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
        List all active tunnels
        
        Returns:
            List[Dict]: List of tunnel information
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
        Get tunnel information
        
        Args:
            tunnel_id: Tunnel ID
            
        Returns:
            TunnelInfo: Tunnel information, returns None if not found
        """
        return self.active_tunnels.get(tunnel_id)
    
    def cleanup_all_tunnels(self) -> None:
        """Clean up all tunnels"""
        tunnel_ids = list(self.active_tunnels.keys())
        
        for tunnel_id in tunnel_ids:
            try:
                self.destroy_tunnel(tunnel_id)
            except Exception as e:
                logger.error(f"Failed to cleanup tunnel {tunnel_id}: {e}")
        
        logger.info(f"Cleaned up {len(tunnel_ids)} tunnels")