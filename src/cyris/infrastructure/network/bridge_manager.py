"""
Bridge Manager

This module manages network bridges for cyber range networking,
including creation, configuration, and cleanup of virtual network bridges.
"""

# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import logging  # Keep for type annotations
import subprocess
import ipaddress
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time

from ..providers.base_provider import InfrastructureError


@dataclass
class BridgeConfig:
    """Configuration for a network bridge"""
    bridge_name: str
    network_cidr: str
    gateway_ip: Optional[str] = None
    dhcp_enabled: bool = False
    dhcp_range_start: Optional[str] = None
    dhcp_range_end: Optional[str] = None
    mtu: int = 1500
    stp_enabled: bool = False  # Spanning Tree Protocol
    forward_delay: int = 15
    hello_time: int = 2
    max_age: int = 20


@dataclass
class BridgeInfo:
    """Information about a network bridge"""
    bridge_name: str
    bridge_id: str
    ip_address: Optional[str]
    network_cidr: str
    state: str  # "up", "down", "unknown"
    interfaces: List[str]
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BridgeManager:
    """
    Network bridge management service.
    
    This service manages virtual network bridges for cyber range networking,
    providing isolation and connectivity between virtual machines.
    
    Capabilities:
    - Create and configure Linux bridges
    - Manage bridge interfaces and ports
    - Set up network isolation
    - Configure bridge parameters (STP, MTU, etc.)
    - Clean up bridge resources
    
    Follows SOLID principles:
    - Single Responsibility: Focuses on bridge management
    - Open/Closed: Extensible for different bridge types
    - Interface Segregation: Focused bridge operations
    - Dependency Inversion: Uses abstract network interfaces
    """
    
    def __init__(
        self,
        bridge_prefix: str = "cyris",
        config_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize bridge manager.
        
        Args:
            bridge_prefix: Prefix for created bridge names
            config_dir: Directory to store bridge configurations
            logger: Optional logger instance
        """
        self.bridge_prefix = bridge_prefix
        self.config_dir = Path(config_dir) if config_dir else Path("/tmp/cyris/bridges")
        self.logger = logger or get_logger(__name__, "bridge_manager")
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Active bridges tracking
        self._bridges: Dict[str, BridgeInfo] = {}
        
        # Load existing bridges from config
        self._load_bridge_configs()
        
        self.logger.info("BridgeManager initialized")
    
    def create_bridge(
        self,
        range_id: str,
        network_name: str,
        config: BridgeConfig
    ) -> str:
        """
        Create a new network bridge.
        
        Args:
            range_id: Cyber range identifier
            network_name: Name of the network
            config: Bridge configuration
        
        Returns:
            Bridge identifier
        
        Raises:
            InfrastructureError: If bridge creation fails
        """
        bridge_name = f"{self.bridge_prefix}-{range_id}-{network_name}"
        
        if bridge_name in self._bridges:
            raise InfrastructureError(f"Bridge {bridge_name} already exists")
        
        self.logger.info(f"Creating bridge {bridge_name} with CIDR {config.network_cidr}")
        
        try:
            # Create the bridge
            self._run_command(["ip", "link", "add", "name", bridge_name, "type", "bridge"])
            
            # Configure bridge parameters
            if config.stp_enabled:
                self._run_command(["ip", "link", "set", "dev", bridge_name, "type", "bridge", "stp_state", "1"])
                self._run_command(["ip", "link", "set", "dev", bridge_name, "type", "bridge", 
                                "forward_delay", str(config.forward_delay)])
                self._run_command(["ip", "link", "set", "dev", bridge_name, "type", "bridge", 
                                "hello_time", str(config.hello_time)])
                self._run_command(["ip", "link", "set", "dev", bridge_name, "type", "bridge", 
                                "max_age", str(config.max_age)])
            
            # Set MTU
            if config.mtu != 1500:
                self._run_command(["ip", "link", "set", "dev", bridge_name, "mtu", str(config.mtu)])
            
            # Bring bridge up
            self._run_command(["ip", "link", "set", "dev", bridge_name, "up"])
            
            # Assign IP address if specified
            gateway_ip = config.gateway_ip
            if not gateway_ip and config.network_cidr:
                # Use first IP in the network as gateway
                network = ipaddress.ip_network(config.network_cidr, strict=False)
                gateway_ip = str(list(network.hosts())[0])
            
            if gateway_ip:
                self._run_command(["ip", "addr", "add", f"{gateway_ip}/{network.prefixlen}", 
                                 "dev", bridge_name])
            
            # Create bridge info
            bridge_info = BridgeInfo(
                bridge_name=bridge_name,
                bridge_id=bridge_name,  # For Linux bridges, name is the ID
                ip_address=gateway_ip,
                network_cidr=config.network_cidr,
                state="up",
                interfaces=[],
                created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                metadata={
                    "range_id": range_id,
                    "network_name": network_name,
                    "mtu": config.mtu,
                    "stp_enabled": config.stp_enabled
                }
            )
            
            # Register bridge
            self._bridges[bridge_name] = bridge_info
            
            # Save configuration
            self._save_bridge_config(bridge_name, config, bridge_info)
            
            self.logger.info(f"Successfully created bridge {bridge_name}")
            return bridge_name
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create bridge {bridge_name}: {e}")
            # Attempt cleanup
            try:
                self._run_command(["ip", "link", "del", bridge_name], check=False)
            except:
                pass
            raise InfrastructureError(f"Bridge creation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error creating bridge {bridge_name}: {e}")
            raise InfrastructureError(f"Bridge creation failed: {e}")
    
    def delete_bridge(self, bridge_id: str) -> None:
        """
        Delete a network bridge.
        
        Args:
            bridge_id: Bridge identifier
        
        Raises:
            InfrastructureError: If bridge deletion fails
        """
        bridge_info = self._bridges.get(bridge_id)
        if not bridge_info:
            self.logger.warning(f"Bridge {bridge_id} not found in registry")
            return
        
        self.logger.info(f"Deleting bridge {bridge_id}")
        
        try:
            # Bring bridge down first
            self._run_command(["ip", "link", "set", "dev", bridge_id, "down"], check=False)
            
            # Delete the bridge
            self._run_command(["ip", "link", "del", bridge_id])
            
            # Remove from registry
            del self._bridges[bridge_id]
            
            # Remove configuration file
            config_file = self.config_dir / f"{bridge_id}.json"
            if config_file.exists():
                config_file.unlink()
            
            self.logger.info(f"Successfully deleted bridge {bridge_id}")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to delete bridge {bridge_id}: {e}")
            raise InfrastructureError(f"Bridge deletion failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error deleting bridge {bridge_id}: {e}")
            raise InfrastructureError(f"Bridge deletion failed: {e}")
    
    def add_interface_to_bridge(self, bridge_id: str, interface_name: str) -> None:
        """
        Add an interface to a bridge.
        
        Args:
            bridge_id: Bridge identifier
            interface_name: Name of the interface to add
        
        Raises:
            InfrastructureError: If operation fails
        """
        bridge_info = self._bridges.get(bridge_id)
        if not bridge_info:
            raise InfrastructureError(f"Bridge {bridge_id} not found")
        
        self.logger.info(f"Adding interface {interface_name} to bridge {bridge_id}")
        
        try:
            # Add interface to bridge
            self._run_command(["ip", "link", "set", "dev", interface_name, "master", bridge_id])
            
            # Update bridge info
            if interface_name not in bridge_info.interfaces:
                bridge_info.interfaces.append(interface_name)
            
            self.logger.info(f"Successfully added interface {interface_name} to bridge {bridge_id}")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to add interface {interface_name} to bridge {bridge_id}: {e}")
            raise InfrastructureError(f"Failed to add interface to bridge: {e}")
    
    def remove_interface_from_bridge(self, bridge_id: str, interface_name: str) -> None:
        """
        Remove an interface from a bridge.
        
        Args:
            bridge_id: Bridge identifier
            interface_name: Name of the interface to remove
        
        Raises:
            InfrastructureError: If operation fails
        """
        bridge_info = self._bridges.get(bridge_id)
        if not bridge_info:
            raise InfrastructureError(f"Bridge {bridge_id} not found")
        
        self.logger.info(f"Removing interface {interface_name} from bridge {bridge_id}")
        
        try:
            # Remove interface from bridge
            self._run_command(["ip", "link", "set", "dev", interface_name, "nomaster"])
            
            # Update bridge info
            if interface_name in bridge_info.interfaces:
                bridge_info.interfaces.remove(interface_name)
            
            self.logger.info(f"Successfully removed interface {interface_name} from bridge {bridge_id}")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to remove interface {interface_name} from bridge {bridge_id}: {e}")
            raise InfrastructureError(f"Failed to remove interface from bridge: {e}")
    
    def get_bridge_info(self, bridge_id: str) -> Optional[BridgeInfo]:
        """Get information about a bridge"""
        return self._bridges.get(bridge_id)
    
    def list_bridges(self, range_id: Optional[str] = None) -> List[BridgeInfo]:
        """
        List all bridges, optionally filtered by range ID.
        
        Args:
            range_id: Optional range ID to filter by
        
        Returns:
            List of bridge information
        """
        bridges = list(self._bridges.values())
        
        if range_id:
            bridges = [
                b for b in bridges 
                if b.metadata and b.metadata.get("range_id") == range_id
            ]
        
        return bridges
    
    def cleanup_range_bridges(self, range_id: str) -> int:
        """
        Clean up all bridges for a specific range.
        
        Args:
            range_id: Range identifier
        
        Returns:
            Number of bridges cleaned up
        """
        range_bridges = self.list_bridges(range_id)
        cleaned_count = 0
        
        for bridge_info in range_bridges:
            try:
                self.delete_bridge(bridge_info.bridge_id)
                cleaned_count += 1
            except Exception as e:
                self.logger.error(f"Failed to cleanup bridge {bridge_info.bridge_id}: {e}")
        
        self.logger.info(f"Cleaned up {cleaned_count} bridges for range {range_id}")
        return cleaned_count
    
    def get_bridge_statistics(self) -> Dict[str, Any]:
        """Get bridge manager statistics"""
        total_bridges = len(self._bridges)
        active_bridges = len([b for b in self._bridges.values() if b.state == "up"])
        
        # Count by range
        range_counts = {}
        for bridge in self._bridges.values():
            if bridge.metadata and "range_id" in bridge.metadata:
                range_id = bridge.metadata["range_id"]
                range_counts[range_id] = range_counts.get(range_id, 0) + 1
        
        return {
            "total_bridges": total_bridges,
            "active_bridges": active_bridges,
            "inactive_bridges": total_bridges - active_bridges,
            "ranges_with_bridges": len(range_counts),
            "bridges_per_range": range_counts
        }
    
    def _run_command(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a system command"""
        self.logger.debug(f"Running command: {' '.join(command)}")
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=check
        )
        
        if result.returncode != 0 and check:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error output: {result.stderr}")
        
        return result
    
    def _save_bridge_config(
        self, 
        bridge_name: str, 
        config: BridgeConfig, 
        bridge_info: BridgeInfo
    ) -> None:
        """Save bridge configuration to file"""
        config_data = {
            "bridge_config": {
                "bridge_name": config.bridge_name,
                "network_cidr": config.network_cidr,
                "gateway_ip": config.gateway_ip,
                "dhcp_enabled": config.dhcp_enabled,
                "dhcp_range_start": config.dhcp_range_start,
                "dhcp_range_end": config.dhcp_range_end,
                "mtu": config.mtu,
                "stp_enabled": config.stp_enabled,
                "forward_delay": config.forward_delay,
                "hello_time": config.hello_time,
                "max_age": config.max_age
            },
            "bridge_info": {
                "bridge_name": bridge_info.bridge_name,
                "bridge_id": bridge_info.bridge_id,
                "ip_address": bridge_info.ip_address,
                "network_cidr": bridge_info.network_cidr,
                "state": bridge_info.state,
                "interfaces": bridge_info.interfaces,
                "created_at": bridge_info.created_at,
                "metadata": bridge_info.metadata
            }
        }
        
        config_file = self.config_dir / f"{bridge_name}.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def _load_bridge_configs(self) -> None:
        """Load bridge configurations from disk"""
        if not self.config_dir.exists():
            return
        
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file) as f:
                    config_data = json.load(f)
                
                bridge_info_data = config_data.get("bridge_info", {})
                if bridge_info_data:
                    bridge_info = BridgeInfo(**bridge_info_data)
                    self._bridges[bridge_info.bridge_id] = bridge_info
                
            except Exception as e:
                self.logger.warning(f"Failed to load bridge config from {config_file}: {e}")