"""
VM IP Address Management

This module provides utilities to discover and manage IP addresses of 
virtual machines in CyRIS, supporting multiple methods to retrieve VM IPs.
"""

import logging
import subprocess
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta

try:
    import libvirt
    LIBVIRT_AVAILABLE = True
except ImportError:
    LIBVIRT_AVAILABLE = False


@dataclass
class VMIPInfo:
    """Information about a VM's IP addresses"""
    vm_name: str
    vm_id: str
    ip_addresses: List[str]
    mac_addresses: List[str]
    interface_names: List[str]
    discovery_method: str
    last_updated: str
    status: str  # "active", "inactive", "unknown"


@dataclass
class CachedIPInfo:
    """Cached IP information with expiration"""
    ip_info: VMIPInfo
    cached_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.now() > self.expires_at
    
    def is_fresh(self, max_age_seconds: int = 300) -> bool:
        """Check if cache entry is fresh (within max_age_seconds)"""
        return (datetime.now() - self.cached_at).total_seconds() < max_age_seconds


@dataclass
class VMHealthInfo:
    """VM health and status information with direct error reporting"""
    vm_name: str
    vm_id: str
    libvirt_status: str  # "running", "shut off", "paused", etc.
    is_healthy: bool     # Simple healthy/unhealthy flag
    boot_time: Optional[str]
    uptime: Optional[str]
    ip_addresses: List[str]
    mac_addresses: List[str]
    network_reachable: bool
    disk_path: str
    error_details: List[str]  # Direct error messages from underlying systems
    last_checked: str
    
    def get_compact_status(self) -> str:
        """Get a single-line status description for compact display"""
        if self.is_healthy:
            return self.ip_addresses[0] if self.ip_addresses else 'healthy'
        
        # For unhealthy VMs, show the most relevant error in a compact form
        if self.error_details:
            # Prioritize certain types of errors
            for error in self.error_details:
                if "AES-encrypted" in error:
                    return "encrypted disk"
                elif "Failed to get shared" in error and "write" in error:
                    return "disk locked"
                elif "Disk file does not exist" in error:
                    return "disk missing"
                elif "no IP address" in error:
                    return "no IP"
                elif "not reachable" in error:
                    return "network down"
            
            # If no specific error pattern matches, show first error truncated
            first_error = self.error_details[0]
            if len(first_error) > 40:
                return first_error[:37] + "..."
            return first_error
        
        return "unhealthy"


class VMIPManager:
    """
    VM IP Address Discovery and Management
    
    This class provides multiple methods to discover IP addresses of VMs:
    1. libvirt domifaddr (most reliable for active VMs)
    2. virsh domifaddr command
    3. ARP table scanning
    4. Network bridge interface scanning
    5. DHCP lease file parsing
    6. Custom CyRIS address calculation
    
    Follows SOLID principles:
    - Single Responsibility: Focus on IP discovery and management
    - Open/Closed: Extensible for new discovery methods
    - Interface Segregation: Specific IP discovery operations
    - Dependency Inversion: Abstract discovery interfaces
    """
    
    def __init__(
        self,
        libvirt_uri: str = "qemu:///system",
        dhcp_lease_dir: str = "/var/lib/dhcp",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize VM IP Manager.
        
        Args:
            libvirt_uri: libvirt connection URI
            dhcp_lease_dir: Directory containing DHCP lease files
            logger: Optional logger instance
        """
        self.libvirt_uri = libvirt_uri
        self.dhcp_lease_dir = dhcp_lease_dir
        self.logger = logger or logging.getLogger(__name__)
        
        # libvirt connection
        self.connection = None
        if LIBVIRT_AVAILABLE:
            try:
                self.connection = libvirt.open(libvirt_uri)
            except libvirt.libvirtError as e:
                self.logger.warning(f"Failed to connect to libvirt: {e}")
        
        # Cache for IP information with expiration
        self._ip_cache: Dict[str, CachedIPInfo] = {}
        
        self.logger.info(f"VMIPManager initialized with URI: {libvirt_uri}")
    
    def get_vm_ip_addresses(
        self, 
        vm_name: str,
        methods: Optional[List[str]] = None,
        timeout: int = 30
    ) -> Optional[VMIPInfo]:
        """
        Get IP addresses for a VM using multiple discovery methods.
        
        Args:
            vm_name: Name of the virtual machine
            methods: List of methods to try (None = try all)
            timeout: Maximum time to wait for IP discovery
            
        Returns:
            VMIPInfo object with discovered IP information, or None if not found
            
        Available methods:
        - 'cyris_topology': Use CyRIS topology manager assigned IP (highest priority)
        - 'libvirt': Use libvirt Python API (most reliable)
        - 'virsh': Use virsh command line tool
        - 'arp': Scan ARP table for MAC-to-IP mappings
        - 'dhcp': Parse DHCP lease files
        - 'bridge': Scan bridge interfaces
        - 'cyris': Use CyRIS-specific calculation method
        """
        if methods is None:
            methods = ['cyris_topology', 'libvirt', 'virsh', 'arp', 'dhcp', 'bridge']
        
        self.logger.info(f"Discovering IP addresses for VM: {vm_name}")
        
        # Try each discovery method
        for method in methods:
            try:
                vm_info = None
                
                if method == 'cyris_topology':
                    vm_info = self._get_ips_via_cyris_topology(vm_name)
                elif method == 'libvirt' and self.connection:
                    vm_info = self._get_ips_via_libvirt(vm_name)
                elif method == 'virsh':
                    vm_info = self._get_ips_via_virsh(vm_name)
                elif method == 'arp':
                    vm_info = self._get_ips_via_arp(vm_name)
                elif method == 'dhcp':
                    vm_info = self._get_ips_via_dhcp_leases(vm_name)
                elif method == 'bridge':
                    vm_info = self._get_ips_via_bridge_scan(vm_name)
                elif method == 'cyris':
                    vm_info = self._get_ips_via_cyris_calculation(vm_name)
                
                if vm_info and vm_info.ip_addresses:
                    vm_info.discovery_method = method
                    vm_info.last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Cache the result with expiration
                    self._ip_cache[vm_name] = CachedIPInfo(ip_info=vm_info)
                    
                    self.logger.info(
                        f"Successfully discovered IPs for {vm_name} using {method}: "
                        f"{', '.join(vm_info.ip_addresses)}"
                    )
                    return vm_info
                    
            except Exception as e:
                self.logger.debug(f"Method {method} failed for VM {vm_name}: {e}")
                continue
        
        self.logger.warning(f"Could not discover IP addresses for VM: {vm_name}")
        return None

    def _get_ips_via_cyris_topology(self, vm_name: str) -> Optional[VMIPInfo]:
        """
        Get IP addresses from CyRIS topology manager assignments.
        KISS: Simple method focused on single purpose.
        """
        try:
            # KISS: Extract guest ID first
            guest_id = self._extract_guest_id_from_vm_name(vm_name)
            if not guest_id:
                return None
            
            # KISS: Get IP assignment from metadata
            assigned_ip = self._get_assigned_ip_from_metadata(guest_id)
            if not assigned_ip:
                return None
            
            # Verify that the assigned IP is actually reachable
            if not self._test_network_reachability(assigned_ip):
                self.logger.debug(f"Assigned IP {assigned_ip} for {vm_name} is not reachable")
                return None
            
            # KISS: Create and return VM info
            return VMIPInfo(
                vm_name=vm_name,
                vm_id=guest_id,
                ip_addresses=[assigned_ip],
                mac_addresses=self._get_vm_mac_addresses(vm_name),
                interface_names=['eth0'],
                discovery_method="cyris_topology",
                last_updated=time.strftime("%Y-%m-%d %H:%M:%S"),
                status="assigned"
            )
            
        except Exception as e:
            self.logger.debug(f"CyRIS topology method failed for {vm_name}: {e}")
        
        return None
    
    def _extract_guest_id_from_vm_name(self, vm_name: str) -> Optional[str]:
        """Extract guest ID from VM name (format: cyris-{guest_id}-{uuid})"""
        parts = vm_name.split('-')
        if len(parts) >= 3 and parts[0] == 'cyris':
            return parts[1]
        return None
    
    def _get_assigned_ip_from_metadata(self, guest_id: str) -> Optional[str]:
        """Get assigned IP address from range metadata"""
        from pathlib import Path
        import json
        
        metadata_file = Path.cwd() / "cyber_range" / "ranges_metadata.json"
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                ranges_data = json.load(f)
            
            # Search through all ranges for IP assignments
            for range_metadata in ranges_data.values():
                tags = range_metadata.get('tags', {})
                if 'ip_assignments' in tags:
                    ip_assignments = json.loads(tags['ip_assignments'])
                    if guest_id in ip_assignments:
                        return ip_assignments[guest_id]
            
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            pass
        
        return None
    
    def _get_ips_via_libvirt(self, vm_name: str) -> Optional[VMIPInfo]:
        """Get IP addresses using libvirt Python API"""
        if not self.connection:
            return None
        
        try:
            domain = self.connection.lookupByName(vm_name)
            if not domain:
                return None
            
            # Check if domain is active
            if domain.state()[0] != libvirt.VIR_DOMAIN_RUNNING:
                return VMIPInfo(
                    vm_name=vm_name,
                    vm_id=domain.UUIDString(),
                    ip_addresses=[],
                    mac_addresses=[],
                    interface_names=[],
                    discovery_method="libvirt",
                    last_updated="",
                    status="inactive"
                )
            
            # Get interface addresses
            interfaces = domain.interfaceAddresses(
                libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE
            )
            
            ip_addresses = []
            mac_addresses = []
            interface_names = []
            
            for interface, data in interfaces.items():
                interface_names.append(interface)
                if 'hwaddr' in data:
                    mac_addresses.append(data['hwaddr'])
                
                if data.get('addrs'):
                    for addr_info in data['addrs']:
                        if addr_info.get('type') == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                            ip_addresses.append(addr_info['addr'])
            
            return VMIPInfo(
                vm_name=vm_name,
                vm_id=domain.UUIDString(),
                ip_addresses=ip_addresses,
                mac_addresses=mac_addresses,
                interface_names=interface_names,
                discovery_method="libvirt",
                last_updated="",
                status="active"
            )
            
        except libvirt.libvirtError as e:
            self.logger.debug(f"libvirt method failed for {vm_name}: {e}")
            return None
    
    def _get_ips_via_virsh(self, vm_name: str) -> Optional[VMIPInfo]:
        """Get IP addresses using virsh command"""
        try:
            # Try domifaddr command
            result = subprocess.run(
                ["virsh", "--connect", self.libvirt_uri, "domifaddr", vm_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            ip_addresses = []
            mac_addresses = []
            interface_names = []
            
            # Parse virsh output
            lines = result.stdout.strip().split('\n')
            for line in lines[2:]:  # Skip header lines
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        interface_names.append(parts[0])
                        mac_addresses.append(parts[1])
                        # IP address is in format "192.168.1.100/24"
                        ip_with_prefix = parts[3]
                        ip_addr = ip_with_prefix.split('/')[0]
                        ip_addresses.append(ip_addr)
            
            if ip_addresses:
                return VMIPInfo(
                    vm_name=vm_name,
                    vm_id=vm_name,  # Use name as ID for virsh
                    ip_addresses=ip_addresses,
                    mac_addresses=mac_addresses,
                    interface_names=interface_names,
                    discovery_method="virsh",
                    last_updated="",
                    status="active"
                )
            
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"virsh method failed for {vm_name}: {e}")
        
        return None
    
    def _get_ips_via_arp(self, vm_name: str) -> Optional[VMIPInfo]:
        """Get IP addresses by scanning ARP table for VM MAC addresses"""
        try:
            # First get MAC addresses for the VM
            mac_addresses = self._get_vm_mac_addresses(vm_name)
            if not mac_addresses:
                return None
            
            # Scan ARP table
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                check=True
            )
            
            ip_addresses = []
            found_macs = []
            
            # Parse ARP output: hostname (192.168.1.100) at 52:54:00:12:34:56 [ether] on br0
            for line in result.stdout.split('\n'):
                for mac in mac_addresses:
                    if mac.lower() in line.lower():
                        # Extract IP address from line
                        ip_match = re.search(r'\(([\d.]+)\)', line)
                        if ip_match:
                            ip_addr = ip_match.group(1)
                            if ip_addr not in ip_addresses:
                                ip_addresses.append(ip_addr)
                                found_macs.append(mac)
            
            if ip_addresses:
                return VMIPInfo(
                    vm_name=vm_name,
                    vm_id=vm_name,
                    ip_addresses=ip_addresses,
                    mac_addresses=found_macs,
                    interface_names=[],
                    discovery_method="arp",
                    last_updated="",
                    status="active"
                )
            
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"ARP method failed for {vm_name}: {e}")
        
        return None
    
    def _get_ips_via_dhcp_leases(self, vm_name: str) -> Optional[VMIPInfo]:
        """Get IP addresses from DHCP lease files"""
        try:
            # Get MAC addresses for the VM
            mac_addresses = self._get_vm_mac_addresses(vm_name)
            if not mac_addresses:
                return None
            
            # Common DHCP lease file locations
            lease_files = [
                "/var/lib/dhcp/dhcpd.leases",
                "/var/lib/dhcpcd5/dhcpcd.leases",
                "/var/lib/NetworkManager/dhcpcd.leases"
            ]
            
            ip_addresses = []
            found_macs = []
            
            for lease_file in lease_files:
                try:
                    with open(lease_file, 'r') as f:
                        content = f.read()
                        
                        # Parse DHCP lease format
                        lease_blocks = content.split('lease ')
                        for block in lease_blocks[1:]:  # Skip first empty block
                            lines = block.split('\n')
                            if lines:
                                ip_addr = lines[0].split()[0]  # First line has IP
                                
                                # Look for MAC address in the block
                                for line in lines:
                                    if 'hardware ethernet' in line:
                                        lease_mac = line.split()[-1].rstrip(';')
                                        if lease_mac.lower() in [m.lower() for m in mac_addresses]:
                                            ip_addresses.append(ip_addr)
                                            found_macs.append(lease_mac)
                                            break
                    
                    if ip_addresses:
                        break
                        
                except (FileNotFoundError, PermissionError):
                    continue
            
            if ip_addresses:
                return VMIPInfo(
                    vm_name=vm_name,
                    vm_id=vm_name,
                    ip_addresses=ip_addresses,
                    mac_addresses=found_macs,
                    interface_names=[],
                    discovery_method="dhcp",
                    last_updated="",
                    status="active"
                )
            
        except Exception as e:
            self.logger.debug(f"DHCP method failed for {vm_name}: {e}")
        
        return None
    
    def _get_ips_via_bridge_scan(self, vm_name: str) -> Optional[VMIPInfo]:
        """Get IP addresses by scanning bridge interfaces"""
        try:
            # Get list of bridges
            result = subprocess.run(
                ["brctl", "show"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # This is a more complex method that would require
            # scanning each bridge and correlating with VM interfaces
            # For now, return None as this is more implementation-intensive
            self.logger.debug("Bridge scanning method not fully implemented")
            return None
            
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Bridge method failed for {vm_name}: {e}")
        
        return None
    
    def _get_ips_via_cyris_calculation(self, vm_name: str) -> Optional[VMIPInfo]:
        """Get IP addresses using CyRIS-specific calculation method"""
        try:
            # Get MAC address for the VM
            mac_addresses = self._get_vm_mac_addresses(vm_name)
            if not mac_addresses:
                return None
            
            ip_addresses = []
            
            # Use CyRIS logic from initif script
            for mac in mac_addresses:
                mac_parts = mac.split(':')
                if len(mac_parts) == 6:
                    # Convert hex MAC parts to decimal for IP calculation
                    try:
                        # Based on CyRIS initif logic for /24 networks
                        last_octet = int(mac_parts[5], 16)
                        second_last_octet = int(mac_parts[4], 16)
                        third_last_octet = int(mac_parts[3], 16)
                        
                        # Typical CyRIS calculation (adjust based on actual network config)
                        # This is a simplified version - actual calculation depends on network prefix
                        base_network = "192.168.122"  # Common libvirt default
                        calculated_ip = f"{base_network}.{last_octet}"
                        
                        ip_addresses.append(calculated_ip)
                        
                    except ValueError:
                        continue
            
            if ip_addresses:
                return VMIPInfo(
                    vm_name=vm_name,
                    vm_id=vm_name,
                    ip_addresses=ip_addresses,
                    mac_addresses=mac_addresses,
                    interface_names=[],
                    discovery_method="cyris",
                    last_updated="",
                    status="calculated"
                )
            
        except Exception as e:
            self.logger.debug(f"CyRIS calculation method failed for {vm_name}: {e}")
        
        return None
    
    def _get_vm_mac_addresses(self, vm_name: str) -> List[str]:
        """Get MAC addresses for a VM"""
        mac_addresses = []
        
        try:
            if self.connection:
                # Try libvirt method first
                domain = self.connection.lookupByName(vm_name)
                if domain:
                    xml_desc = domain.XMLDesc()
                    root = ET.fromstring(xml_desc)
                    
                    # Find all interface MAC addresses
                    for interface in root.findall('.//interface/mac'):
                        mac = interface.get('address')
                        if mac:
                            mac_addresses.append(mac)
            
            # If libvirt didn't work, try virsh
            if not mac_addresses:
                result = subprocess.run(
                    ["virsh", "--connect", self.libvirt_uri, "dumpxml", vm_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Parse XML to find MAC addresses
                root = ET.fromstring(result.stdout)
                for interface in root.findall('.//interface/mac'):
                    mac = interface.get('address')
                    if mac:
                        mac_addresses.append(mac)
                        
        except Exception as e:
            self.logger.debug(f"Failed to get MAC addresses for {vm_name}: {e}")
        
        return mac_addresses
    
    def get_all_vm_ips(
        self, 
        vm_names: Optional[List[str]] = None
    ) -> Dict[str, VMIPInfo]:
        """
        Get IP addresses for all VMs or a specific list of VMs.
        
        Args:
            vm_names: List of VM names to check (None = all VMs)
            
        Returns:
            Dictionary of vm_name -> VMIPInfo
        """
        result = {}
        
        if vm_names is None:
            # Discover all VMs
            vm_names = self._discover_all_vms()
        
        for vm_name in vm_names:
            vm_info = self.get_vm_ip_addresses(vm_name)
            if vm_info:
                result[vm_name] = vm_info
        
        return result
    
    def _discover_all_vms(self) -> List[str]:
        """Discover all VM names on the system"""
        vm_names = []
        
        try:
            if self.connection:
                # Get all domains (running and stopped)
                domains = self.connection.listAllDomains()
                vm_names = [domain.name() for domain in domains]
            else:
                # Fall back to virsh
                result = subprocess.run(
                    ["virsh", "--connect", self.libvirt_uri, "list", "--all", "--name"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                vm_names = [name.strip() for name in result.stdout.split('\n') if name.strip()]
                
        except Exception as e:
            self.logger.error(f"Failed to discover VMs: {e}")
        
        return vm_names
    
    def wait_for_vm_ip(
        self, 
        vm_name: str, 
        timeout: int = 120,
        poll_interval: int = 5
    ) -> Optional[VMIPInfo]:
        """
        Wait for a VM to get an IP address after startup.
        
        Args:
            vm_name: Name of the VM
            timeout: Maximum time to wait (seconds)
            poll_interval: Time between checks (seconds)
            
        Returns:
            VMIPInfo when IP is discovered, or None if timeout
        """
        self.logger.info(f"Waiting for VM {vm_name} to get IP address (timeout: {timeout}s)")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            vm_info = self.get_vm_ip_addresses(vm_name)
            if vm_info and vm_info.ip_addresses:
                self.logger.info(
                    f"VM {vm_name} got IP address: {', '.join(vm_info.ip_addresses)}"
                )
                return vm_info
            
            self.logger.debug(f"VM {vm_name} IP not ready, waiting {poll_interval}s...")
            time.sleep(poll_interval)
        
        self.logger.warning(f"Timeout waiting for VM {vm_name} IP address")
        return None
    
    def get_cached_ip_info(self, vm_name: str, max_age_seconds: int = 300) -> Optional[VMIPInfo]:
        """
        Get cached IP information for a VM if it's fresh.
        
        Args:
            vm_name: Name of the VM
            max_age_seconds: Maximum age of cache entry in seconds (default: 5 minutes)
            
        Returns:
            VMIPInfo if cache is fresh, None if expired or not found
        """
        cached_entry = self._ip_cache.get(vm_name)
        if cached_entry and not cached_entry.is_expired() and cached_entry.is_fresh(max_age_seconds):
            return cached_entry.ip_info
        
        # Remove expired cache entry
        if cached_entry and cached_entry.is_expired():
            self._ip_cache.pop(vm_name, None)
            
        return None
    
    def get_vm_health_info(self, vm_name: str) -> VMHealthInfo:
        """
        Get VM health information with direct error reporting.
        
        Instead of trying to categorize all possible failure modes,
        this method collects and reports actual error messages from
        the underlying systems (libvirt, qemu, network, etc.).
        
        Args:
            vm_name: Name of the virtual machine
            
        Returns:
            VMHealthInfo object with direct error details
        """
        error_details = []
        
        # Initialize with defaults
        health_info = VMHealthInfo(
            vm_name=vm_name,
            vm_id="unknown",
            libvirt_status="unknown",
            is_healthy=False,
            boot_time=None,
            uptime=None,
            ip_addresses=[],
            mac_addresses=[],
            network_reachable=False,
            disk_path="unknown",
            error_details=[],
            last_checked=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # Try libvirt connection first, fall back to virsh if needed
        use_virsh_fallback = False
        
        if not self.connection:
            if not LIBVIRT_AVAILABLE:
                self.logger.debug("libvirt Python module not available, using virsh fallback")
                use_virsh_fallback = True
            else:
                error_details.append("libvirt connection not available")
                health_info.error_details = error_details
                use_virsh_fallback = True
        
        if use_virsh_fallback:
            return self._get_vm_health_via_virsh(vm_name, health_info, error_details)
        
        try:
            # Get libvirt domain
            domain = self.connection.lookupByName(vm_name)
            health_info.vm_id = domain.UUIDString()
            
            # Get libvirt status
            state, reason = domain.state()
            state_names = {
                libvirt.VIR_DOMAIN_NOSTATE: 'nostate',
                libvirt.VIR_DOMAIN_RUNNING: 'running',
                libvirt.VIR_DOMAIN_BLOCKED: 'blocked',
                libvirt.VIR_DOMAIN_PAUSED: 'paused',
                libvirt.VIR_DOMAIN_SHUTDOWN: 'shutdown',
                libvirt.VIR_DOMAIN_SHUTOFF: 'shut off',
                libvirt.VIR_DOMAIN_CRASHED: 'crashed',
                libvirt.VIR_DOMAIN_PMSUSPENDED: 'suspended'
            }
            health_info.libvirt_status = state_names.get(state, f'unknown({state})')
            
            # Check disk configuration and collect any disk errors
            self._check_vm_disk_errors(domain, health_info, error_details)
            
            # If VM is not running, collect relevant error information and return
            if state != libvirt.VIR_DOMAIN_RUNNING:
                health_info.is_healthy = False
                if state == libvirt.VIR_DOMAIN_CRASHED:
                    error_details.append("VM has crashed according to libvirt")
                elif state == libvirt.VIR_DOMAIN_SHUTOFF:
                    error_details.append("VM is shut off - may have failed to boot")
                health_info.error_details = error_details
                return health_info
            
            # VM is running according to libvirt - check if it's actually functional
            
            # Get boot time and uptime
            self._get_vm_timing_info(domain, health_info)
            
            # Try to get IP addresses - collect any errors during IP discovery
            try:
                vm_ip_info = self.get_vm_ip_addresses(vm_name)
                if vm_ip_info:
                    health_info.ip_addresses = vm_ip_info.ip_addresses
                    health_info.mac_addresses = vm_ip_info.mac_addresses
            except Exception as e:
                error_details.append(f"IP discovery failed: {e}")
            
            # Test network reachability if we have IPs
            if health_info.ip_addresses:
                try:
                    health_info.network_reachable = self._test_network_reachability(health_info.ip_addresses[0])
                    if not health_info.network_reachable:
                        error_details.append(f"VM has IP {health_info.ip_addresses[0]} but is not reachable via ping")
                except Exception as e:
                    error_details.append(f"Network reachability test failed: {e}")
            
            # Simple health determination: healthy if we have IP and network
            health_info.is_healthy = bool(health_info.ip_addresses and health_info.network_reachable)
            
            # If VM is running but we have no IP, that's likely an error
            if not health_info.ip_addresses:
                error_details.append("VM appears running in virsh but has no IP address")
                if health_info.uptime:
                    error_details.append(f"VM uptime: {health_info.uptime}")
                
                # Try additional IP discovery methods
                try:
                    self._try_alternative_ip_discovery(vm_name, health_info, error_details)
                except Exception as e:
                    error_details.append(f"Alternative IP discovery failed: {e}")
                
                # Try to get more diagnostic info by examining QEMU/console logs
                try:
                    self._collect_vm_diagnostic_info(vm_name, error_details)
                except Exception as e:
                    error_details.append(f"Could not collect additional diagnostics: {e}")
            
        except libvirt.libvirtError as e:
            error_details.append(f"libvirt error: {e}")
            health_info.is_healthy = False
        except Exception as e:
            error_details.append(f"Health check failed: {e}")
            health_info.is_healthy = False
        
        health_info.error_details = error_details
        return health_info
    
    def _check_vm_disk_errors(self, domain, health_info: VMHealthInfo, error_details: List[str]):
        """Check VM disk and collect any error information"""
        try:
            xml_desc = domain.XMLDesc()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_desc)
            
            # Find disk elements
            disks = root.findall('.//disk[@type="file"][@device="disk"]')
            if not disks:
                error_details.append("No disk found in VM configuration")
                return
            
            # Check first disk (primary boot disk)
            disk = disks[0]
            source = disk.find('source')
            if source is not None:
                disk_path = source.get('file')
                health_info.disk_path = disk_path
                
                if not disk_path:
                    error_details.append("Disk path not specified in VM configuration")
                    return
                
                # Check if disk file exists
                from pathlib import Path
                disk_file = Path(disk_path)
                if not disk_file.exists():
                    error_details.append(f"Disk file does not exist: {disk_path}")
                    return
                
                # Check disk image with qemu-img and capture any errors
                # KISS: Skip disk check for running VMs to avoid lock issues
                try:
                    result = subprocess.run(
                        ["qemu-img", "info", "--force-share", disk_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Look for common issues in qemu-img output
                    if "AES-encrypted" in result.stdout:
                        error_details.append(f"Disk image is AES-encrypted: {disk_path}")
                    elif "backing file:" in result.stdout:
                        # Check backing file exists
                        for line in result.stdout.split('\n'):
                            if line.startswith('backing file:'):
                                backing_file = line.split(':', 1)[1].strip()
                                backing_path = Path(backing_file)
                                if not backing_path.exists():
                                    error_details.append(f"Backing file missing: {backing_file}")
                                    
                except subprocess.CalledProcessError as e:
                    error_details.append(f"qemu-img check failed for {disk_path}: {e}")
                    if e.stderr:
                        # Clean up stderr - replace newlines with semicolons for compact display
                        clean_stderr = e.stderr.strip().replace('\n', '; ')
                        error_details.append(f"qemu-img stderr: {clean_stderr}")
                except Exception as e:
                    error_details.append(f"Disk check error for {disk_path}: {e}")
            else:
                error_details.append("Disk has no source file specified")
                
        except Exception as e:
            error_details.append(f"Could not parse VM XML for disk information: {e}")
    
    def _try_alternative_ip_discovery(self, vm_name: str, health_info: VMHealthInfo, error_details: List[str]):
        """Try alternative methods to discover VM IP addresses"""
        # Method 1: Check if VM is on a different bridge network
        try:
            # Get VM's current bridge/network connections
            result = subprocess.run(
                ["virsh", "--connect", self.libvirt_uri, "dumpxml", vm_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(result.stdout)
            
            # Find network interfaces and their bridges
            interfaces = root.findall('.//interface[@type="bridge"]')
            for interface in interfaces:
                source = interface.find('source')
                if source is not None:
                    bridge_name = source.get('bridge')
                    if bridge_name and bridge_name != 'virbr0':
                        error_details.append(f"VM is connected to custom bridge: {bridge_name}")
                        
                        # Try to scan the bridge's network
                        bridge_ip = self._get_bridge_ip(bridge_name)
                        if bridge_ip:
                            error_details.append(f"Bridge {bridge_name} IP: {bridge_ip}")
                            # Try to scan the bridge network for the VM
                            discovered_ip = self._scan_bridge_network(bridge_name, health_info.mac_addresses)
                            if discovered_ip:
                                health_info.ip_addresses.append(discovered_ip)
                                error_details.append(f"Found VM IP via bridge scan: {discovered_ip}")
                        else:
                            error_details.append(f"Could not determine IP range for bridge: {bridge_name}")
                    else:
                        error_details.append(f"VM is connected to default libvirt bridge: {bridge_name or 'virbr0'}")
        except Exception as e:
            error_details.append(f"Bridge analysis failed: {e}")
        
        # Method 2: Try to find IP by scanning all known networks
        if not health_info.ip_addresses and health_info.mac_addresses:
            try:
                discovered_ip = self._network_scan_for_mac(health_info.mac_addresses[0])
                if discovered_ip:
                    health_info.ip_addresses.append(discovered_ip)
                    error_details.append(f"Found VM IP via network scan: {discovered_ip}")
            except Exception as e:
                error_details.append(f"Network scan failed: {e}")

    def _get_bridge_ip(self, bridge_name: str) -> Optional[str]:
        """Get the IP address/network of a bridge"""
        try:
            result = subprocess.run(
                ["ip", "addr", "show", bridge_name],
                capture_output=True,
                text=True,
                check=True
            )
            # Look for inet lines
            for line in result.stdout.split('\n'):
                if 'inet ' in line and not '127.0.0.1' in line:
                    # Extract IP/prefix
                    parts = line.strip().split()
                    for part in parts:
                        if '/' in part and not part.startswith('127.'):
                            return part.split('/')[0]  # Return just the IP
        except Exception:
            pass
        return None

    def _scan_bridge_network(self, bridge_name: str, mac_addresses: List[str]) -> Optional[str]:
        """Scan a bridge network to find a VM by MAC address"""
        if not mac_addresses:
            return None
            
        try:
            bridge_ip = self._get_bridge_ip(bridge_name)
            if not bridge_ip:
                return None
            
            # Calculate network range (assume /24)
            network_base = '.'.join(bridge_ip.split('.')[:-1])
            
            # Quick scan of common DHCP range
            for i in range(2, 50):  # Common DHCP range
                test_ip = f"{network_base}.{i}"
                try:
                    # Quick ping test
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", test_ip],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        # Check if this IP has the VM's MAC
                        arp_result = subprocess.run(
                            ["arp", "-n", test_ip],
                            capture_output=True,
                            text=True
                        )
                        for mac in mac_addresses:
                            if mac.lower() in arp_result.stdout.lower():
                                return test_ip
                except:
                    continue
        except Exception:
            pass
        return None

    def _network_scan_for_mac(self, mac_address: str) -> Optional[str]:
        """Scan common network ranges to find VM by MAC address"""
        common_ranges = [
            "192.168.1",
            "192.168.0", 
            "192.168.122",
            "10.0.0",
            "172.16.0"
        ]
        
        for network_base in common_ranges:
            for i in range(2, 20):  # Quick scan of first few addresses
                test_ip = f"{network_base}.{i}"
                try:
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", test_ip],
                        capture_output=True,
                        timeout=1
                    )
                    if result.returncode == 0:
                        arp_result = subprocess.run(
                            ["arp", "-n", test_ip],
                            capture_output=True,
                            text=True
                        )
                        if mac_address.lower() in arp_result.stdout.lower():
                            return test_ip
                except:
                    continue
        return None

    def _collect_vm_diagnostic_info(self, vm_name: str, error_details: List[str]):
        """Collect additional diagnostic information about VM problems"""
        try:
            # Try to get console log or QEMU monitor info
            result = subprocess.run(
                ["virsh", "--connect", self.libvirt_uri, "console", vm_name, "--force"],
                capture_output=True,
                text=True,
                timeout=2  # Short timeout since we just want to check if console is accessible
            )
        except subprocess.TimeoutExpired:
            error_details.append("Console appears to be responsive (timeout on console connection)")
        except subprocess.CalledProcessError as e:
            error_details.append(f"Console check failed: {e}")
        except Exception as e:
            error_details.append(f"Could not check console: {e}")
            
        # Try to check VM domain info
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.libvirt_uri, "dominfo", vm_name],
                capture_output=True,
                text=True,
                check=True
            )
            # Look for useful information in domain info
            for line in result.stdout.split('\n'):
                if 'Max memory:' in line or 'Used memory:' in line:
                    error_details.append(f"Domain info: {line.strip()}")
        except subprocess.CalledProcessError as e:
            error_details.append(f"Could not get domain info: {e}")
    
    def _check_vm_disk_status(self, domain, health_info: VMHealthInfo, issues: List[str], warnings: List[str]):
        """Check VM disk status and configuration"""
        try:
            xml_desc = domain.XMLDesc()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_desc)
            
            # Find disk elements
            disks = root.findall('.//disk[@type="file"][@device="disk"]')
            if not disks:
                health_info.disk_status = "no-disk"
                issues.append("No disk found in VM configuration")
                return
            
            # Check first disk (primary boot disk)
            disk = disks[0]
            source = disk.find('source')
            if source is not None:
                disk_path = source.get('file')
                health_info.disk_path = disk_path
                
                if not disk_path:
                    health_info.disk_status = "missing-path"
                    issues.append("Disk path not specified")
                    return
                
                # Check if disk file exists
                from pathlib import Path
                disk_file = Path(disk_path)
                if not disk_file.exists():
                    health_info.disk_status = "missing-file"
                    issues.append(f"Disk file does not exist: {disk_path}")
                    return
                
                # Check disk image info
                try:
                    result = subprocess.run(
                        ["qemu-img", "info", disk_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    if "AES-encrypted" in result.stdout:
                        health_info.disk_status = "encrypted"
                        issues.append("Disk image is encrypted - may cause boot failure")
                    elif "backing file:" in result.stdout:
                        health_info.disk_status = "overlay"
                        # Check backing file
                        for line in result.stdout.split('\n'):
                            if line.startswith('backing file:'):
                                backing_file = line.split(':', 1)[1].strip()
                                backing_path = Path(backing_file)
                                if not backing_path.exists():
                                    health_info.disk_status = "missing-backing"
                                    issues.append(f"Backing file missing: {backing_file}")
                                    return
                        
                        if health_info.disk_status == "overlay":
                            health_info.disk_status = "ok"
                    else:
                        health_info.disk_status = "ok"
                        
                except subprocess.CalledProcessError as e:
                    health_info.disk_status = "check-failed"
                    warnings.append(f"Could not check disk image: {e}")
                except Exception as e:
                    health_info.disk_status = "unknown"
                    warnings.append(f"Disk check error: {e}")
            else:
                health_info.disk_status = "no-source"
                issues.append("Disk has no source file specified")
                
        except Exception as e:
            health_info.disk_status = "xml-error"
            warnings.append(f"Could not parse VM XML: {e}")
    
    def _get_vm_timing_info(self, domain, health_info: VMHealthInfo):
        """Get VM boot time and uptime information"""
        try:
            # Get domain info for uptime calculation
            info = domain.info()
            cpu_time_ns = info[4]  # CPU time in nanoseconds
            
            # Try to get more detailed timing from domain stats
            try:
                stats = domain.getCPUStats(total=True)
                if stats and len(stats) > 0 and 'cpu_time' in stats[0]:
                    cpu_time_ns = stats[0]['cpu_time']
            except:
                pass
            
            # This is an approximation - actual boot time would need guest agent
            if cpu_time_ns > 0:
                uptime_seconds = cpu_time_ns // 1000000000  # Convert to seconds
                if uptime_seconds > 60:
                    health_info.uptime = f"{uptime_seconds // 60} minutes"
                else:
                    health_info.uptime = f"{uptime_seconds} seconds"
            
        except Exception:
            # If we can't get timing info, that's not critical
            pass
    
    def _test_network_reachability(self, ip_address: str) -> bool:
        """Test if VM is reachable over the network"""
        try:
            # KISS: More lenient network test with longer timeout
            result = subprocess.run(
                ["ping", "-c", "3", "-W", "5", ip_address],
                capture_output=True,
                timeout=15
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_vm_resource_usage(self, domain, health_info: VMHealthInfo, warnings: List[str]):
        """Get VM resource usage information"""
        try:
            # Get basic domain info
            info = domain.info()
            max_memory = info[1]  # in KB
            current_memory = info[2]  # in KB
            
            if max_memory > 0:
                health_info.memory_usage = (current_memory / max_memory) * 100
            
            # Try to get CPU stats (this might not always work)
            try:
                cpu_stats = domain.getCPUStats(total=True)
                if cpu_stats and len(cpu_stats) > 0:
                    # This is a simplified CPU usage calculation
                    health_info.cpu_usage = min(100.0, cpu_stats[0].get('cpu_time', 0) / 10000000)
            except:
                pass  # CPU stats not critical
                
        except Exception as e:
            warnings.append(f"Could not get resource usage: {e}")
    
    def _get_vm_health_via_virsh(self, vm_name: str, health_info: VMHealthInfo, 
                                error_details: List[str]) -> VMHealthInfo:
        """Get VM health information using virsh commands as fallback"""
        try:
            # Get VM state using virsh with correct libvirt URI
            result = subprocess.run(
                ["virsh", "--connect", self.libvirt_uri, "domstate", vm_name],
                capture_output=True,
                text=True,
                check=True
            )
            health_info.libvirt_status = result.stdout.strip()
            
            # Get VM ID using virsh
            try:
                uuid_result = subprocess.run(
                    ["virsh", "--connect", self.libvirt_uri, "domuuid", vm_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
                health_info.vm_id = uuid_result.stdout.strip()
            except Exception as e:
                error_details.append(f"Could not get VM UUID: {e}")
                health_info.vm_id = "unknown"
            
            # Check if VM is running
            if health_info.libvirt_status.lower() != "running":
                health_info.is_healthy = False
                if health_info.libvirt_status.lower() == "crashed":
                    error_details.append("VM has crashed according to virsh")
                elif health_info.libvirt_status.lower() == "shut off":
                    error_details.append("VM is shut off - may have failed to boot")
                
                # Check disk status even when not running
                self._check_vm_disk_via_virsh(vm_name, health_info, error_details)
            else:
                # VM is running - check disk and network
                self._check_vm_disk_via_virsh(vm_name, health_info, error_details)
                
                # Try to get IP addresses
                try:
                    vm_ip_info = self.get_vm_ip_addresses(vm_name)
                    if vm_ip_info:
                        health_info.ip_addresses = vm_ip_info.ip_addresses
                        health_info.mac_addresses = vm_ip_info.mac_addresses
                except Exception as e:
                    error_details.append(f"IP discovery failed via virsh: {e}")
                
                # Test network reachability
                if health_info.ip_addresses:
                    try:
                        health_info.network_reachable = self._test_network_reachability(health_info.ip_addresses[0])
                        if not health_info.network_reachable:
                            error_details.append(f"VM has IP {health_info.ip_addresses[0]} but is not reachable")
                    except Exception as e:
                        error_details.append(f"Network reachability test failed: {e}")
                
                # Simple health determination
                health_info.is_healthy = bool(health_info.ip_addresses and health_info.network_reachable)
                
                # If running but no IP, collect diagnostic info
                if not health_info.ip_addresses:
                    error_details.append("VM appears running in virsh but has no IP address")
                    
                    # Try alternative IP discovery methods
                    try:
                        self._try_alternative_ip_discovery(vm_name, health_info, error_details)
                    except Exception as e:
                        error_details.append(f"Alternative IP discovery failed: {e}")
                    
                    self._collect_vm_diagnostic_info(vm_name, error_details)
                    
                # Get basic uptime info
                try:
                    uptime_result = subprocess.run(
                        ["virsh", "--connect", self.libvirt_uri, "dominfo", vm_name],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    if "running" in uptime_result.stdout.lower():
                        health_info.uptime = "running (exact time unavailable)"
                except Exception as e:
                    error_details.append(f"Could not get uptime info: {e}")
            
        except subprocess.CalledProcessError as e:
            error_details.append(f"virsh command failed: {e}")
            if "not found" in str(e).lower():
                error_details.append(f"VM not found: {vm_name}")
            health_info.is_healthy = False
        except Exception as e:
            error_details.append(f"Health check failed via virsh: {e}")
            health_info.is_healthy = False
        
        health_info.error_details = error_details
        return health_info
    
    def _check_vm_disk_via_virsh(self, vm_name: str, health_info: VMHealthInfo, 
                                error_details: List[str]):
        """Check VM disk status using virsh commands and collect error details"""
        try:
            # Get VM XML using virsh with correct libvirt URI
            result = subprocess.run(
                ["virsh", "--connect", self.libvirt_uri, "dumpxml", vm_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Use the same disk checking logic as the libvirt version
            import xml.etree.ElementTree as ET
            root = ET.fromstring(result.stdout)
            
            # Find disk elements
            disks = root.findall('.//disk[@type="file"][@device="disk"]')
            if not disks:
                error_details.append("No disk found in VM configuration")
                return
            
            # Check first disk (primary boot disk)
            disk = disks[0]
            source = disk.find('source')
            if source is not None:
                disk_path = source.get('file')
                health_info.disk_path = disk_path
                
                if not disk_path:
                    error_details.append("Disk path not specified in VM configuration")
                    return
                
                # Check if disk file exists
                from pathlib import Path
                disk_file = Path(disk_path)
                if not disk_file.exists():
                    error_details.append(f"Disk file does not exist: {disk_path}")
                    return
                
                # Check disk image with qemu-img and capture any errors
                # KISS: Skip disk check for running VMs to avoid lock issues
                try:
                    img_result = subprocess.run(
                        ["qemu-img", "info", "--force-share", disk_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Look for common issues in qemu-img output
                    if "AES-encrypted" in img_result.stdout:
                        error_details.append(f"Disk image is AES-encrypted: {disk_path}")
                    elif "backing file:" in img_result.stdout:
                        # Check backing file exists
                        for line in img_result.stdout.split('\n'):
                            if line.startswith('backing file:'):
                                backing_file = line.split(':', 1)[1].strip()
                                backing_path = Path(backing_file)
                                if not backing_path.exists():
                                    error_details.append(f"Backing file missing: {backing_file}")
                                    
                except subprocess.CalledProcessError as e:
                    error_details.append(f"qemu-img check failed for {disk_path}: {e}")
                    if e.stderr:
                        # Clean up stderr - replace newlines with semicolons for compact display
                        clean_stderr = e.stderr.strip().replace('\n', '; ')
                        error_details.append(f"qemu-img stderr: {clean_stderr}")
                except Exception as e:
                    error_details.append(f"Disk check error for {disk_path}: {e}")
            else:
                error_details.append("Disk has no source file specified")
                
        except Exception as e:
            error_details.append(f"Could not parse VM XML via virsh: {e}")

    def clear_cache(self, vm_name: Optional[str] = None) -> None:
        """Clear IP cache for a specific VM or all VMs"""
        if vm_name:
            self._ip_cache.pop(vm_name, None)
        else:
            self._ip_cache.clear()
    
    def close(self):
        """Close connections and cleanup resources"""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass


def get_vm_ips_cli(vm_name: str, libvirt_uri: str = "qemu:///system") -> Optional[VMIPInfo]:
    """
    Convenience function for CLI usage to get VM IP addresses.
    
    Args:
        vm_name: Name of the virtual machine
        libvirt_uri: libvirt URI to connect to
        
    Returns:
        VMIPInfo object or None if not found
    """
    manager = VMIPManager(libvirt_uri=libvirt_uri)
    try:
        return manager.get_vm_ip_addresses(vm_name)
    finally:
        manager.close()


if __name__ == "__main__":
    # Example usage
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python vm_ip_manager.py <vm_name> [libvirt_uri]")
        sys.exit(1)
    
    vm_name = sys.argv[1]
    libvirt_uri = sys.argv[2] if len(sys.argv) > 2 else "qemu:///system"
    
    vm_info = get_vm_ips_cli(vm_name, libvirt_uri)
    
    if vm_info:
        print(f"VM: {vm_info.vm_name}")
        print(f"Status: {vm_info.status}")
        print(f"IP Addresses: {', '.join(vm_info.ip_addresses)}")
        print(f"MAC Addresses: {', '.join(vm_info.mac_addresses)}")
        print(f"Discovery Method: {vm_info.discovery_method}")
    else:
        print(f"Could not find IP addresses for VM: {vm_name}")
        sys.exit(1)