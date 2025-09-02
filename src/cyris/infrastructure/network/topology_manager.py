"""
Network Topology Management

This module handles the creation and management of network topologies
for cyber ranges based on YAML specifications.
"""

import logging
import ipaddress
import subprocess
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

import libvirt


class NetworkTopologyManager:
    """
    Manages network topology creation for cyber ranges.
    
    Handles:
    - Network segment creation
    - IP address assignment
    - Firewall rules
    - Bridge management
    - DHCP configuration
    """
    
    def __init__(self, libvirt_connection=None):
        """
        Initialize topology manager.
        
        Args:
            libvirt_connection: Optional libvirt connection
        """
        self.libvirt_connection = libvirt_connection
        self.logger = logging.getLogger(__name__)
        self.networks = {}  # network_name -> network_info
        self.ip_assignments = {}  # guest_id -> ip_address
        self.discovered_ips = {}  # vm_name -> discovered_ip
        self.metadata_path = Path('/home/ubuntu/cyris/cyber_range/ranges_metadata.json')
    
    def create_topology(
        self, 
        topology_config: Dict[str, Any],
        guests: List[Any],
        range_id: str
    ) -> Dict[str, str]:
        """
        Create network topology based on configuration.
        
        Args:
            topology_config: Topology configuration from YAML
            guests: List of guest configurations
            range_id: Unique range identifier
        
        Returns:
            Dictionary mapping guest_id to assigned IP address
        """
        self.logger.info(f"Creating network topology for range {range_id}")
        
        # Create networks defined in topology
        if 'networks' in topology_config:
            for network_config in topology_config['networks']:
                network_name = network_config['name']
                self._create_network_segment(network_name, network_config, range_id)
        
        # Assign IP addresses to guests based on network membership
        self._assign_guest_ips(topology_config, guests, range_id)
        
        # Configure firewall rules if specified
        if 'forwarding_rules' in topology_config:
            self._configure_forwarding_rules(topology_config['forwarding_rules'], range_id)
        
        return self.ip_assignments
    
    def _create_network_segment(
        self, 
        network_name: str, 
        network_config: Dict[str, Any],
        range_id: str
    ) -> str:
        """Create a network segment for the cyber range"""
        
        # Generate unique network name
        full_network_name = f"cyris-{range_id}-{network_name}"
        
        # Determine network CIDR based on network name or use default
        network_cidrs = {
            'office': '192.168.100.0/24',
            'servers': '192.168.200.0/24', 
            'dmz': '192.168.50.0/24',
            'management': '192.168.122.0/24'
        }
        
        network_cidr = network_cidrs.get(network_name, '192.168.150.0/24')
        
        # Parse network for gateway assignment
        network = ipaddress.ip_network(network_cidr, strict=False)
        gateway_ip = str(list(network.hosts())[0])  # First host as gateway
        
        # Create libvirt network XML
        network_xml = self._generate_network_xml(
            full_network_name, 
            network_cidr, 
            gateway_ip,
            network_config
        )
        
        # Create network in libvirt if available
        if self.libvirt_connection:
            try:
                # Check if network already exists
                try:
                    existing_network = self.libvirt_connection.networkLookupByName(full_network_name)
                    self.logger.info(f"Network {full_network_name} already exists")
                except libvirt.libvirtError:
                    # Network doesn't exist, create it
                    network = self.libvirt_connection.networkDefineXML(network_xml)
                    if network:
                        network.create()
                        network.setAutostart(True)
                        self.logger.info(f"Created network {full_network_name}")
                    
            except Exception as e:
                self.logger.warning(f"Failed to create libvirt network {full_network_name}: {e}")
        
        # Store network info
        self.networks[network_name] = {
            'full_name': full_network_name,
            'cidr': network_cidr,
            'gateway': gateway_ip,
            'config': network_config
        }
        
        return full_network_name
    
    def _generate_network_xml(
        self, 
        network_name: str, 
        network_cidr: str, 
        gateway_ip: str,
        config: Dict[str, Any]
    ) -> str:
        """Generate libvirt XML configuration for network"""
        
        network = ipaddress.ip_network(network_cidr, strict=False)
        netmask = str(network.netmask)
        
        # DHCP range - use middle portion of network
        hosts = list(network.hosts())
        dhcp_start = str(hosts[10]) if len(hosts) > 20 else str(hosts[1])
        dhcp_end = str(hosts[-10]) if len(hosts) > 20 else str(hosts[-2])
        
        bridge_name = config.get('bridge', f"br-{network_name}")
        
        xml = f"""
<network>
  <name>{network_name}</name>
  <bridge name='{bridge_name}' stp='on' delay='0'/>
  <forward mode='nat'/>
  <ip address='{gateway_ip}' netmask='{netmask}'>
    <dhcp>
      <range start='{dhcp_start}' end='{dhcp_end}'/>
    </dhcp>
  </ip>
</network>
        """.strip()
        
        return xml
    
    def _assign_guest_ips(
        self, 
        topology_config: Dict[str, Any], 
        guests: List[Any],
        range_id: str
    ) -> None:
        """Assign IP addresses to guests based on network membership"""
        
        # Build network membership map
        network_members = {}  # network_name -> [guest_id.interface]
        
        if 'networks' in topology_config:
            for network_config in topology_config['networks']:
                network_name = network_config['name']
                members = network_config.get('members', [])
                
                # Parse members (format: guest_id.eth0)
                for member in members:
                    if isinstance(member, str):
                        member_parts = member.split('.')
                        if len(member_parts) >= 1:
                            guest_id = member_parts[0]
                            interface = member_parts[1] if len(member_parts) > 1 else 'eth0'
                            
                            if network_name not in network_members:
                                network_members[network_name] = []
                            network_members[network_name].append((guest_id, interface))
        
        # Assign IPs based on predefined addresses or network membership
        for guest in guests:
            # Get guest ID with backward compatibility
            if hasattr(guest, 'guest_id'):
                guest_id = guest.guest_id
            elif hasattr(guest, 'id') and not isinstance(guest.id, property):
                guest_id = guest.id
            else:
                guest_id = getattr(guest, 'guest_id', 'unknown')
            
            # Check if guest has predefined IP address
            if hasattr(guest, 'ip_addr') and guest.ip_addr:
                self.ip_assignments[guest_id] = guest.ip_addr
                self.logger.info(f"Assigned predefined IP {guest.ip_addr} to guest {guest_id}")
                continue
            
            # Find network membership and assign IP
            assigned = False
            for network_name, members in network_members.items():
                for member_guest_id, interface in members:
                    if member_guest_id == guest_id:
                        # Assign IP from this network
                        if network_name in self.networks:
                            network_info = self.networks[network_name]
                            network = ipaddress.ip_network(network_info['cidr'], strict=False)
                            
                            # Use guest ID hash to get consistent IP assignment
                            host_offset = hash(guest_id) % (network.num_addresses - 20) + 10
                            guest_ip = str(list(network.hosts())[host_offset])
                            
                            self.ip_assignments[guest_id] = guest_ip
                            self.logger.info(f"Assigned network IP {guest_ip} to guest {guest_id} in network {network_name}")
                            assigned = True
                            break
                if assigned:
                    break
            
            # Fallback: assign from default network
            if not assigned:
                default_network = ipaddress.ip_network('192.168.122.0/24', strict=False)
                host_offset = hash(guest_id) % 200 + 50  # Avoid conflicts
                fallback_ip = str(list(default_network.hosts())[host_offset])
                self.ip_assignments[guest_id] = fallback_ip
                self.logger.info(f"Assigned fallback IP {fallback_ip} to guest {guest_id}")
    
    def _configure_forwarding_rules(
        self, 
        forwarding_rules: List[Dict[str, Any]],
        range_id: str
    ) -> None:
        """Configure firewall forwarding rules for network topology"""
        
        self.logger.info(f"Configuring {len(forwarding_rules)} forwarding rules for range {range_id}")
        
        # Generate iptables rules for forwarding
        iptables_rules = []
        
        for rule in forwarding_rules:
            if 'rule' in rule:
                rule_spec = rule['rule']
                
                # Parse rule: "src=office dst=servers dport=25,53"
                rule_parts = rule_spec.split()
                src_networks = []
                dst_networks = []
                sports = []
                dports = []
                
                for part in rule_parts:
                    if part.startswith('src='):
                        src_networks = part.split('=')[1].split(',')
                    elif part.startswith('dst='):
                        dst_networks = part.split('=')[1].split(',')
                    elif part.startswith('sport='):
                        sports = part.split('=')[1].split(',')
                    elif part.startswith('dport='):
                        dports = part.split('=')[1].split(',')
                
                # Generate iptables rules for each combination
                for src in src_networks:
                    for dst in dst_networks:
                        src_network = self.networks.get(src, {}).get('cidr', '0.0.0.0/0')
                        dst_network = self.networks.get(dst, {}).get('cidr', '0.0.0.0/0')
                        
                        for dport in (dports or ['any']):
                            if dport != 'any':
                                iptables_rule = f"iptables -A FORWARD -s {src_network} -d {dst_network} -p tcp --dport {dport} -j ACCEPT"
                            else:
                                iptables_rule = f"iptables -A FORWARD -s {src_network} -d {dst_network} -j ACCEPT"
                            
                            iptables_rules.append(iptables_rule)
        
        # Store rules for later application
        if hasattr(self, 'forwarding_rules'):
            self.forwarding_rules.extend(iptables_rules)
        else:
            self.forwarding_rules = iptables_rules
    
    def destroy_topology(self, range_id: str) -> None:
        """Destroy network topology for cyber range"""
        
        self.logger.info(f"Destroying network topology for range {range_id}")
        
        # Destroy libvirt networks
        if self.libvirt_connection:
            for network_info in self.networks.values():
                network_name = network_info['full_name']
                try:
                    network = self.libvirt_connection.networkLookupByName(network_name)
                    if network.isActive():
                        network.destroy()
                    network.undefine()
                    self.logger.info(f"Destroyed network {network_name}")
                except libvirt.libvirtError:
                    self.logger.warning(f"Network {network_name} not found or already destroyed")
        
        # Clear internal state
        self.networks.clear()
        self.ip_assignments.clear()
    
    def get_guest_ip(self, guest_id: str) -> Optional[str]:
        """Get assigned IP address for a guest"""
        return self.ip_assignments.get(guest_id)
    
    def get_network_info(self, network_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a network"""
        return self.networks.get(network_name)
    
    def apply_forwarding_rules(self) -> None:
        """Apply configured firewall forwarding rules"""
        if hasattr(self, 'forwarding_rules'):
            for rule in self.forwarding_rules:
                try:
                    subprocess.run(rule.split(), check=False, capture_output=True)
                    self.logger.debug(f"Applied rule: {rule}")
                except Exception as e:
                    self.logger.warning(f"Failed to apply rule {rule}: {e}")
    
    def discover_vm_ips(self, vm_names: List[str], kvm_provider=None) -> Dict[str, str]:
        """
        Discover actual IP addresses of running VMs.
        
        Args:
            vm_names: List of VM names to discover IPs for
            kvm_provider: KVM provider instance for IP discovery
            
        Returns:
            Dictionary mapping VM name to discovered IP address
        """
        self.logger.info(f"Discovering IPs for {len(vm_names)} VMs")
        
        discovered = {}
        
        for vm_name in vm_names:
            try:
                # Method 1: Use KVM provider's IP discovery if available
                if kvm_provider:
                    ip = kvm_provider.get_vm_ip(vm_name)
                    if ip:
                        discovered[vm_name] = ip
                        self.discovered_ips[vm_name] = ip
                        self.logger.info(f"Discovered IP via KVM provider: {vm_name} -> {ip}")
                        continue
                
                # Method 2: Try virsh domifaddr
                ip = self._discover_ip_virsh(vm_name)
                if ip:
                    discovered[vm_name] = ip
                    self.discovered_ips[vm_name] = ip
                    self.logger.info(f"Discovered IP via virsh: {vm_name} -> {ip}")
                    continue
                    
                # Method 3: Try DHCP lease scan
                ip = self._discover_ip_dhcp_leases(vm_name)
                if ip:
                    discovered[vm_name] = ip
                    self.discovered_ips[vm_name] = ip
                    self.logger.info(f"Discovered IP via DHCP leases: {vm_name} -> {ip}")
                    continue
                    
                # Method 4: Try network scanning
                ip = self._discover_ip_network_scan(vm_name)
                if ip:
                    discovered[vm_name] = ip
                    self.discovered_ips[vm_name] = ip
                    self.logger.info(f"Discovered IP via network scan: {vm_name} -> {ip}")
                    continue
                    
                self.logger.warning(f"Could not discover IP for VM: {vm_name}")
                
            except Exception as e:
                self.logger.error(f"Error discovering IP for VM {vm_name}: {e}")
        
        return discovered
    
    def sync_metadata(self, range_id: str, ip_mappings: Dict[str, str]) -> None:
        """
        Synchronize IP mappings to persistent metadata storage.
        
        Args:
            range_id: Range identifier
            ip_mappings: Dictionary of VM name to IP address mappings
        """
        try:
            # Load existing metadata
            metadata = {}
            if self.metadata_path.exists():
                with open(self.metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            # Update range metadata
            if range_id not in metadata:
                metadata[range_id] = {
                    'created_at': datetime.now().isoformat(),
                    'vm_ips': {},
                    'networks': {},
                    'last_updated': datetime.now().isoformat()
                }
            
            # Update IP mappings
            metadata[range_id]['vm_ips'].update(ip_mappings)
            metadata[range_id]['last_updated'] = datetime.now().isoformat()
            
            # Add network topology info
            metadata[range_id]['networks'] = {
                name: {
                    'cidr': info['cidr'],
                    'gateway': info['gateway'],
                    'full_name': info['full_name']
                }
                for name, info in self.networks.items()
            }
            
            # Write back to file
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            self.logger.info(f"Synchronized metadata for range {range_id}: {len(ip_mappings)} IP mappings")
            
        except Exception as e:
            self.logger.error(f"Failed to sync metadata for range {range_id}: {e}")
    
    def get_range_metadata(self, range_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific range.
        
        Args:
            range_id: Range identifier
            
        Returns:
            Range metadata dictionary or None if not found
        """
        try:
            if self.metadata_path.exists():
                with open(self.metadata_path, 'r') as f:
                    metadata = json.load(f)
                return metadata.get(range_id)
        except Exception as e:
            self.logger.error(f"Failed to get metadata for range {range_id}: {e}")
        return None
    
    def assign_ips(self, guests: List[Any]) -> Dict[str, str]:
        """
        Assign IP addresses to guests based on topology configuration.
        
        Args:
            guests: List of guest configurations
            
        Returns:
            Dictionary mapping guest ID to assigned IP address
        """
        self.logger.info(f"Assigning IPs to {len(guests)} guests")
        
        assignments = {}
        
        for guest in guests:
            # Get guest ID with backward compatibility
            if hasattr(guest, 'guest_id'):
                guest_id = guest.guest_id
            elif hasattr(guest, 'id') and not isinstance(guest.id, property):
                guest_id = guest.id
            else:
                guest_id = getattr(guest, 'guest_id', 'unknown')
            
            # Check if guest has predefined IP address
            if hasattr(guest, 'ip_addr') and guest.ip_addr:
                assignments[guest_id] = guest.ip_addr
                self.ip_assignments[guest_id] = guest.ip_addr
                self.logger.info(f"Using predefined IP {guest.ip_addr} for guest {guest_id}")
            else:
                # Assign from available range
                default_network = ipaddress.ip_network('192.168.122.0/24', strict=False)
                host_offset = hash(guest_id) % 200 + 50
                assigned_ip = str(list(default_network.hosts())[host_offset])
                assignments[guest_id] = assigned_ip
                self.ip_assignments[guest_id] = assigned_ip
                self.logger.info(f"Assigned generated IP {assigned_ip} to guest {guest_id}")
        
        return assignments
    
    def _discover_ip_virsh(self, vm_name: str) -> Optional[str]:
        """Discover IP using virsh domifaddr command"""
        try:
            result = subprocess.run([
                'virsh', 'domifaddr', vm_name
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'ipv4' in line.lower():
                        # Parse line like: vnet0      52:54:00:xx:xx:xx    ipv4         192.168.122.xxx/24
                        parts = line.split()
                        for part in parts:
                            if '/' in part and self._is_valid_ip(part.split('/')[0]):
                                return part.split('/')[0]
                                
        except Exception as e:
            self.logger.debug(f"virsh domifaddr failed for {vm_name}: {e}")
            
        return None
    
    def _discover_ip_dhcp_leases(self, vm_name: str) -> Optional[str]:
        """Discover IP from DHCP lease files"""
        lease_files = [
            '/var/lib/libvirt/dnsmasq/virbr0.status',
            '/var/lib/libvirt/dnsmasq/default.leases',
            '/var/lib/dhcp/dhcpd.leases'
        ]
        
        for lease_file in lease_files:
            try:
                if Path(lease_file).exists():
                    with open(lease_file, 'r') as f:
                        content = f.read()
                        
                        # Look for VM name in lease content
                        if vm_name in content:
                            # Try to extract IP addresses from the content
                            import re
                            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
                            ips = re.findall(ip_pattern, content)
                            
                            for ip in ips:
                                if self._is_valid_ip(ip):
                                    return ip
                                    
            except Exception as e:
                self.logger.debug(f"DHCP lease scan failed for {lease_file}: {e}")
                
        return None
    
    def _discover_ip_network_scan(self, vm_name: str) -> Optional[str]:
        """Discover IP by scanning common network ranges"""
        common_ranges = [
            '192.168.122.0/24',  # Default libvirt
            '192.168.100.0/24',  # Office network
            '192.168.200.0/24'   # Server network
        ]
        
        for cidr in common_ranges:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                
                # Test a few likely IPs
                for host_offset in [50, 51, 52, 100, 101, 102]:
                    try:
                        if host_offset < network.num_addresses - 2:
                            test_ip = str(list(network.hosts())[host_offset])
                            
                            # Quick ping test
                            ping_result = subprocess.run([
                                'ping', '-c', '1', '-W', '1', test_ip
                            ], capture_output=True, timeout=2)
                            
                            if ping_result.returncode == 0:
                                # Additional verification could be added here
                                return test_ip
                                
                    except (IndexError, subprocess.TimeoutExpired):
                        continue
                        
            except Exception as e:
                self.logger.debug(f"Network scan failed for {cidr}: {e}")
                
        return None
    
    def _is_valid_ip(self, ip_str: str) -> bool:
        """Check if string is a valid IP address"""
        try:
            ip = ipaddress.ip_address(ip_str)
            # Exclude localhost and link-local
            return not ip_str.startswith(('127.', '169.254.', '0.'))
        except ValueError:
            return False