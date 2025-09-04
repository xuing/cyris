"""
LibVirt Domain Wrapper

Enhanced wrapper for libvirt domain operations with improved error handling,
performance optimizations, and convenient high-level operations.

Usage:
    # Basic usage
    wrapper = LibvirtDomainWrapper.from_name("vm-name")
    ips = wrapper.get_ip_addresses()
    state = wrapper.get_state_info()
    
    # With custom connection manager
    manager = LibvirtConnectionManager("qemu+ssh://remote/system")
    wrapper = LibvirtDomainWrapper.from_name("vm-name", manager)
    
    # Direct from domain object
    domain = conn.lookupByName("vm-name")
    wrapper = LibvirtDomainWrapper(domain)
"""

import libvirt
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import xml.etree.ElementTree as ET
import time
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .libvirt_connection_manager import (
    LibvirtConnectionManager, 
    get_connection_manager,
    LibvirtDomainError
)

logger = get_logger(__name__, "libvirt_domain_wrapper")


class DomainState(Enum):
    """Domain state enumeration"""
    NOSTATE = libvirt.VIR_DOMAIN_NOSTATE
    RUNNING = libvirt.VIR_DOMAIN_RUNNING
    BLOCKED = libvirt.VIR_DOMAIN_BLOCKED
    PAUSED = libvirt.VIR_DOMAIN_PAUSED
    SHUTDOWN = libvirt.VIR_DOMAIN_SHUTDOWN
    SHUTOFF = libvirt.VIR_DOMAIN_SHUTOFF
    CRASHED = libvirt.VIR_DOMAIN_CRASHED
    PMSUSPENDED = libvirt.VIR_DOMAIN_PMSUSPENDED


@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str                    # Interface name (e.g., "vnet0")
    mac_address: str            # MAC address
    ip_addresses: List[str] = field(default_factory=list)    # IPv4/IPv6 addresses
    bridge: Optional[str] = None                            # Connected bridge
    network: Optional[str] = None                           # Network name
    interface_type: str = "bridge"                          # Interface type
    
    @property
    def primary_ip(self) -> Optional[str]:
        """Get primary IPv4 address"""
        ipv4_addresses = [ip for ip in self.ip_addresses if '.' in ip and ':' not in ip]
        return ipv4_addresses[0] if ipv4_addresses else None


@dataclass
class DomainStateInfo:
    """Comprehensive domain state information"""
    name: str
    uuid: str
    state: DomainState
    reason: int
    id: int                      # -1 if not running
    is_active: bool
    is_persistent: bool
    autostart: bool
    
    # Resource information
    max_memory: int              # KB
    memory: int                  # KB  
    vcpus: int
    cpu_time: int               # nanoseconds
    
    # Network information
    interfaces: List[NetworkInterface] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def state_str(self) -> str:
        """Human-readable state"""
        return self.state.name.lower()
    
    @property
    def memory_mb(self) -> float:
        """Memory in MB"""
        return self.memory / 1024.0
    
    @property
    def max_memory_mb(self) -> float:
        """Max memory in MB"""
        return self.max_memory / 1024.0
    
    @property
    def all_ip_addresses(self) -> List[str]:
        """All IP addresses from all interfaces"""
        all_ips = []
        for iface in self.interfaces:
            all_ips.extend(iface.ip_addresses)
        return all_ips
    
    @property
    def primary_ip_address(self) -> Optional[str]:
        """Primary IPv4 address"""
        for iface in self.interfaces:
            primary_ip = iface.primary_ip
            if primary_ip:
                return primary_ip
        return None


@dataclass
class DiskInfo:
    """Domain disk information"""
    target: str                  # Target device (e.g., "vda")
    source: str                 # Source file/device path
    driver_type: str            # Driver type (e.g., "qcow2", "raw")
    device_type: str            # Device type ("disk", "cdrom", etc.)
    bus: str                    # Bus type ("virtio", "ide", etc.)
    readonly: bool = False
    
    @property
    def size_bytes(self) -> Optional[int]:
        """Get disk size in bytes (requires file system access)"""
        try:
            import os
            if os.path.exists(self.source):
                return os.path.getsize(self.source)
        except:
            pass
        return None


class LibvirtDomainWrapper:
    """
    Enhanced wrapper for libvirt domain operations.
    
    Provides high-level operations, improved error handling, and performance
    optimizations for common domain management tasks.
    """
    
    def __init__(
        self, 
        domain: libvirt.virDomain,
        connection_manager: Optional[LibvirtConnectionManager] = None
    ):
        """
        Initialize domain wrapper.
        
        Args:
            domain: LibVirt domain object
            connection_manager: Optional connection manager for advanced operations
        """
        self.domain = domain
        self.connection_manager = connection_manager
        self._cached_xml: Optional[str] = None
        self._xml_cache_time: Optional[datetime] = None
        self._xml_cache_ttl = 300  # 5 minutes
        
        # Basic domain info
        self.name = domain.name()
        self.uuid = domain.UUIDString()
    
    @classmethod
    def from_name(
        cls, 
        domain_name: str, 
        connection_manager: Optional[LibvirtConnectionManager] = None,
        uri: str = "qemu:///system"
    ) -> 'LibvirtDomainWrapper':
        """
        Create wrapper from domain name.
        
        Args:
            domain_name: Name of the domain
            connection_manager: Optional connection manager
            uri: Connection URI (if connection_manager not provided)
            
        Returns:
            Domain wrapper instance
        """
        if connection_manager is None:
            connection_manager = get_connection_manager(uri)
        
        domain = connection_manager.get_domain(domain_name)
        return cls(domain, connection_manager)
    
    def get_ip_addresses(self, timeout: int = 30) -> List[str]:
        """
        Get all IP addresses for the domain using multiple methods.
        
        Args:
            timeout: Maximum time to wait for IP discovery
            
        Returns:
            List of IP addresses
        """
        ip_addresses = []
        
        try:
            # Method 1: libvirt interfaceAddresses (most reliable for active VMs)
            if self.is_active():
                try:
                    interfaces = self.domain.interfaceAddresses(
                        libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE, 
                        0
                    )
                    
                    for interface_name, interface_info in interfaces.items():
                        if interface_info['addrs']:
                            for addr_info in interface_info['addrs']:
                                if addr_info['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                                    ip_addresses.append(addr_info['addr'])
                                elif addr_info['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV6:
                                    # Include IPv6 but prefer IPv4
                                    ip_addresses.append(addr_info['addr'])
                    
                    if ip_addresses:
                        logger.debug(f"Found IPs via libvirt interfaces for {self.name}: {ip_addresses}")
                        return ip_addresses
                        
                except libvirt.libvirtError as e:
                    logger.debug(f"libvirt interfaceAddresses failed for {self.name}: {e}")
            
            # Method 2: Parse domain XML for static IP configuration
            xml_ips = self._extract_ips_from_xml()
            if xml_ips:
                ip_addresses.extend(xml_ips)
                logger.debug(f"Found IPs from XML for {self.name}: {xml_ips}")
            
            # Method 3: DHCP leases (if connection manager available)
            if self.connection_manager and not ip_addresses:
                dhcp_ips = self._get_dhcp_lease_ips()
                if dhcp_ips:
                    ip_addresses.extend(dhcp_ips)
                    logger.debug(f"Found IPs from DHCP leases for {self.name}: {dhcp_ips}")
            
        except Exception as e:
            logger.warning(f"Error discovering IPs for domain {self.name}: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ips = []
        for ip in ip_addresses:
            if ip not in seen:
                seen.add(ip)
                unique_ips.append(ip)
        
        return unique_ips
    
    def _extract_ips_from_xml(self) -> List[str]:
        """Extract IP addresses from domain XML configuration"""
        try:
            xml_desc = self.get_xml_config()
            root = ET.fromstring(xml_desc)
            
            ip_addresses = []
            
            # Look for static IP configurations in interface elements
            for interface in root.findall('.//interface'):
                # Check for IP elements (some configurations include static IPs)
                for ip_elem in interface.findall('.//ip'):
                    address = ip_elem.get('address')
                    if address:
                        ip_addresses.append(address)
            
            return ip_addresses
            
        except Exception as e:
            logger.debug(f"Error parsing XML for IPs in {self.name}: {e}")
            return []
    
    def _get_dhcp_lease_ips(self) -> List[str]:
        """Get IP addresses from DHCP leases"""
        try:
            if not self.connection_manager:
                return []
            
            conn = self.connection_manager.get_connection()
            
            # Get all networks and check DHCP leases
            networks = conn.listAllNetworks()
            mac_addresses = self.get_mac_addresses()
            
            ip_addresses = []
            
            for network in networks:
                try:
                    leases = network.DHCPLeases()
                    for lease in leases:
                        if lease.get('mac') in mac_addresses:
                            ip_addr = lease.get('ipaddr')
                            if ip_addr:
                                ip_addresses.append(ip_addr)
                except libvirt.libvirtError:
                    # Network might not support DHCP leases
                    continue
            
            return ip_addresses
            
        except Exception as e:
            logger.debug(f"Error getting DHCP lease IPs for {self.name}: {e}")
            return []
    
    def get_mac_addresses(self) -> List[str]:
        """Get MAC addresses for all network interfaces"""
        try:
            xml_desc = self.get_xml_config()
            root = ET.fromstring(xml_desc)
            
            mac_addresses = []
            for interface in root.findall('.//interface'):
                mac_elem = interface.find('mac')
                if mac_elem is not None:
                    mac_addr = mac_elem.get('address')
                    if mac_addr:
                        mac_addresses.append(mac_addr)
            
            return mac_addresses
            
        except Exception as e:
            logger.warning(f"Error getting MAC addresses for {self.name}: {e}")
            return []
    
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get detailed network interface information"""
        try:
            xml_desc = self.get_xml_config()
            root = ET.fromstring(xml_desc)
            
            interfaces = []
            
            # Get interface information from XML
            for idx, interface_elem in enumerate(root.findall('.//interface')):
                interface_type = interface_elem.get('type', 'bridge')
                
                # MAC address
                mac_elem = interface_elem.find('mac')
                mac_address = mac_elem.get('address') if mac_elem is not None else f"unknown-{idx}"
                
                # Target device name
                target_elem = interface_elem.find('target')
                target_name = target_elem.get('dev') if target_elem is not None else f"vnet{idx}"
                
                # Source (bridge or network)
                source_elem = interface_elem.find('source')
                bridge = None
                network = None
                
                if source_elem is not None:
                    if interface_type == 'bridge':
                        bridge = source_elem.get('bridge')
                    elif interface_type == 'network':
                        network = source_elem.get('network')
                
                # Create interface object
                interface = NetworkInterface(
                    name=target_name,
                    mac_address=mac_address,
                    bridge=bridge,
                    network=network,
                    interface_type=interface_type
                )
                
                interfaces.append(interface)
            
            # Get IP addresses and assign to interfaces
            ip_addresses = self.get_ip_addresses()
            
            # Try to match IPs to interfaces (simplified approach)
            if interfaces and ip_addresses:
                # For now, assign all IPs to the first interface
                # A more sophisticated approach would match based on MAC/DHCP info
                interfaces[0].ip_addresses = ip_addresses
            
            return interfaces
            
        except Exception as e:
            logger.warning(f"Error getting network interfaces for {self.name}: {e}")
            return []
    
    def get_state_info(self) -> DomainStateInfo:
        """Get comprehensive domain state information"""
        try:
            # Basic state and info
            state, reason = self.domain.state()
            info = self.domain.info()
            domain_id = self.domain.ID() if self.domain.isActive() else -1
            
            # Additional properties
            is_persistent = bool(self.domain.isPersistent())
            autostart = bool(self.domain.autostart())
            
            # Network interfaces
            interfaces = self.get_network_interfaces()
            
            return DomainStateInfo(
                name=self.name,
                uuid=self.uuid,
                state=DomainState(state),
                reason=reason,
                id=domain_id,
                is_active=bool(self.domain.isActive()),
                is_persistent=is_persistent,
                autostart=autostart,
                max_memory=info[1],
                memory=info[2],
                vcpus=info[3],
                cpu_time=info[4],
                interfaces=interfaces
            )
            
        except libvirt.libvirtError as e:
            raise LibvirtDomainError(f"Failed to get state info for {self.name}: {e}")
    
    def get_xml_config(self, flags: int = 0) -> str:
        """
        Get domain XML configuration with caching.
        
        Args:
            flags: XML dump flags
            
        Returns:
            Domain XML configuration
        """
        now = datetime.now()
        
        # Check cache validity
        if (self._cached_xml and self._xml_cache_time and 
            (now - self._xml_cache_time).total_seconds() < self._xml_cache_ttl):
            return self._cached_xml
        
        try:
            xml_desc = self.domain.XMLDesc(flags)
            
            # Cache the result
            self._cached_xml = xml_desc
            self._xml_cache_time = now
            
            return xml_desc
            
        except libvirt.libvirtError as e:
            raise LibvirtDomainError(f"Failed to get XML config for {self.name}: {e}")
    
    def get_disk_info(self) -> List[DiskInfo]:
        """Get disk information for the domain"""
        try:
            xml_desc = self.get_xml_config()
            root = ET.fromstring(xml_desc)
            
            disks = []
            
            for disk_elem in root.findall('.//disk'):
                device_type = disk_elem.get('device', 'disk')
                
                # Target
                target_elem = disk_elem.find('target')
                target = target_elem.get('dev') if target_elem is not None else 'unknown'
                bus = target_elem.get('bus') if target_elem is not None else 'unknown'
                
                # Source
                source_elem = disk_elem.find('source')
                source = ''
                if source_elem is not None:
                    source = (source_elem.get('file') or 
                             source_elem.get('dev') or 
                             source_elem.get('name') or '')
                
                # Driver
                driver_elem = disk_elem.find('driver')
                driver_type = 'raw'
                if driver_elem is not None:
                    driver_type = driver_elem.get('type', 'raw')
                
                # Readonly
                readonly = disk_elem.find('readonly') is not None
                
                disk_info = DiskInfo(
                    target=target,
                    source=source,
                    driver_type=driver_type,
                    device_type=device_type,
                    bus=bus,
                    readonly=readonly
                )
                
                disks.append(disk_info)
            
            return disks
            
        except Exception as e:
            logger.warning(f"Error getting disk info for {self.name}: {e}")
            return []
    
    def is_active(self) -> bool:
        """Check if domain is active (running)"""
        try:
            return bool(self.domain.isActive())
        except libvirt.libvirtError:
            return False
    
    def start(self) -> bool:
        """
        Start the domain.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.is_active():
                logger.info(f"Domain {self.name} is already running")
                return True
            
            self.domain.create()
            logger.info(f"Started domain {self.name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to start domain {self.name}: {e}")
            return False
    
    def shutdown(self, timeout: int = 60) -> bool:
        """
        Gracefully shutdown the domain.
        
        Args:
            timeout: Maximum time to wait for shutdown
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_active():
                logger.info(f"Domain {self.name} is already shut down")
                return True
            
            self.domain.shutdown()
            
            # Wait for shutdown to complete
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.is_active():
                    logger.info(f"Domain {self.name} shut down gracefully")
                    return True
                time.sleep(2)
            
            logger.warning(f"Domain {self.name} did not shut down within {timeout}s")
            return False
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to shutdown domain {self.name}: {e}")
            return False
    
    def destroy(self) -> bool:
        """
        Forcefully destroy (stop) the domain.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_active():
                logger.info(f"Domain {self.name} is already destroyed")
                return True
            
            self.domain.destroy()
            logger.info(f"Destroyed domain {self.name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to destroy domain {self.name}: {e}")
            return False
    
    def undefine(self, remove_storage: bool = False) -> bool:
        """
        Undefine (remove configuration) of the domain.
        
        Args:
            remove_storage: Whether to remove associated storage
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Stop domain first if running
            if self.is_active():
                self.destroy()
            
            flags = 0
            if remove_storage:
                flags |= libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE
                flags |= libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA
            
            self.domain.undefine(flags)
            logger.info(f"Undefined domain {self.name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to undefine domain {self.name}: {e}")
            return False
    
    def destroy_and_undefine(self, remove_storage: bool = False) -> bool:
        """
        Completely remove domain (destroy + undefine).
        
        Args:
            remove_storage: Whether to remove associated storage
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        if self.is_active():
            success &= self.destroy()
        
        success &= self.undefine(remove_storage=remove_storage)
        
        if success:
            logger.info(f"Successfully removed domain {self.name}")
        else:
            logger.error(f"Failed to completely remove domain {self.name}")
        
        return success
    
    def reboot(self, timeout: int = 60) -> bool:
        """
        Reboot the domain.
        
        Args:
            timeout: Maximum time to wait for reboot
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_active():
                logger.warning(f"Cannot reboot inactive domain {self.name}")
                return False
            
            self.domain.reboot()
            logger.info(f"Rebooted domain {self.name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to reboot domain {self.name}: {e}")
            return False
    
    def get_console_output(self, size: int = 1024) -> str:
        """
        Get console output from domain.
        
        Args:
            size: Maximum number of bytes to retrieve
            
        Returns:
            Console output string
        """
        try:
            # This may not be available on all hypervisors
            output = self.domain.qemuMonitorCommand('info capture', 0)
            return output
        except libvirt.libvirtError:
            # Fallback: this feature is not universally available
            logger.debug(f"Console output not available for {self.name}")
            return ""
    
    def __str__(self) -> str:
        """String representation"""
        state = "unknown"
        try:
            state = self.get_state_info().state_str
        except:
            pass
        return f"LibvirtDomainWrapper({self.name}, state={state})"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return f"LibvirtDomainWrapper(name='{self.name}', uuid='{self.uuid}')"