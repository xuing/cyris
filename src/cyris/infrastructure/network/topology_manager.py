"""
Network Topology Management

This module handles the creation and management of network topologies
for cyber ranges based on YAML specifications.
"""

import logging
import ipaddress
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

try:
    import libvirt
    LIBVIRT_AVAILABLE = True
except ImportError:
    LIBVIRT_AVAILABLE = False
    # Mock libvirt for testing
    class MockLibvirt:
        pass
    libvirt = MockLibvirt()


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
        if self.libvirt_connection and LIBVIRT_AVAILABLE:
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
        if self.libvirt_connection and LIBVIRT_AVAILABLE:
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