"""
Layer 3 Network Automation Service

This service provides comprehensive Layer 3 network automation capabilities,
restoring the automatic firewall rule generation and network isolation features
from the legacy CyRIS system.

Key Features:
- Automatic iptables FORWARD rule generation from YAML topology
- Network name to IP range resolution
- Zero-configuration network isolation
- Integration with existing FirewallManager and TopologyManager
"""

import logging
import ipaddress
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# Import existing CyRIS components
from ..infrastructure.network.firewall_manager import FirewallManager, RuleAction
from ..infrastructure.network.topology_manager import NetworkTopologyManager
from ..core.exceptions import CyRISNetworkError, CyRISVirtualizationError
from ..domain.entities.network_policy import NetworkRule, NetworkPolicy


class Layer3NetworkService:
    """
    Comprehensive Layer 3 network automation service.
    
    Provides automatic firewall rule generation from network topology specifications,
    restoring the zero-configuration network isolation capabilities from the legacy system.
    """
    
    def __init__(
        self, 
        firewall_manager: Optional[FirewallManager] = None,
        topology_manager: Optional[NetworkTopologyManager] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize Layer 3 network service.
        
        Args:
            firewall_manager: FirewallManager instance for rule application
            topology_manager: TopologyManager for network topology access
            logger: Optional logger instance
        """
        self.firewall_manager = firewall_manager or FirewallManager()
        self.topology_manager = topology_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize firewall chains if needed
        try:
            self.firewall_manager.initialize_firewall()
        except Exception as e:
            self.logger.warning(f"Firewall initialization warning: {e}")
    
    def process_topology_rules(
        self,
        topology_config: Dict[str, Any],
        range_id: str,
        network_info: Optional[Dict[str, Dict[str, Any]]] = None,
        ip_assignments: Optional[Dict[str, str]] = None
    ) -> NetworkPolicy:
        """
        Process YAML topology forwarding rules into a network policy.
        
        Args:
            topology_config: Topology configuration from YAML
            range_id: Range identifier
            network_info: Network information from topology manager
            ip_assignments: VM IP assignments
            
        Returns:
            NetworkPolicy with parsed rules and generated iptables commands
            
        Raises:
            CyRISNetworkError: If rule processing fails
        """
        self.logger.info(f"Processing Layer 3 topology rules for range {range_id}")
        
        try:
            # Create policy
            policy = NetworkPolicy(
                policy_id=f"layer3-{range_id}",
                range_id=range_id
            )
            
            # Get forwarding rules from topology config
            forwarding_rules = topology_config.get('forwarding_rules', [])
            if not forwarding_rules:
                self.logger.info(f"No forwarding rules specified for range {range_id}")
                return policy
            
            # Build IP mappings from network information
            if network_info:
                for network_name, network_data in network_info.items():
                    if 'cidr' in network_data:
                        policy.ip_mappings[network_name] = network_data['cidr']
            
            # Process each forwarding rule
            for rule_spec in forwarding_rules:
                if 'rule' not in rule_spec:
                    self.logger.warning(f"Skipping invalid rule specification: {rule_spec}")
                    continue
                
                network_rule = self._parse_forwarding_rule(rule_spec['rule'])
                if network_rule:
                    policy.add_rule(network_rule)
            
            # Generate iptables rules
            policy.iptables_rules = self._generate_iptables_rules(policy)
            
            self.logger.info(
                f"Generated {len(policy.iptables_rules)} iptables rules from "
                f"{len(policy.rules)} forwarding specifications"
            )
            
            return policy
            
        except Exception as e:
            raise CyRISNetworkError(
                f"Failed to process topology rules for range {range_id}: {e}",
                operation="process_topology_rules",
                range_id=range_id
            ) from e
    
    def apply_network_policy(self, policy: NetworkPolicy) -> bool:
        """
        Apply network policy using the firewall manager.
        
        Args:
            policy: NetworkPolicy to apply
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            CyRISNetworkError: If policy application fails
        """
        self.logger.info(f"Applying network policy {policy.policy_id} with {len(policy.iptables_rules)} rules")
        
        try:
            # Create firewall policy using existing FirewallManager
            firewall_policy_name = f"cyris-layer3-{policy.range_id}"
            
            # Initialize network policy in firewall manager
            firewall_policy_id = self.firewall_manager.create_network_policy(
                range_id=policy.range_id,
                policy_name=firewall_policy_name,
                description=f"Layer 3 automation for range {policy.range_id}"
            )
            
            # Add each iptables rule to the policy
            for i, rule in enumerate(policy.iptables_rules):
                rule_name = f"layer3-rule-{i+1}"
                
                # Parse iptables rule to extract components
                rule_components = self._parse_iptables_rule(rule)
                
                # Add rule to firewall policy
                self.firewall_manager.add_custom_rule(
                    policy_id=firewall_policy_id,
                    rule_name=rule_name,
                    action=RuleAction.ACCEPT,
                    **rule_components
                )
            
            # Apply the complete policy
            self.firewall_manager.apply_policy(firewall_policy_id)
            self.logger.info(f"Successfully applied network policy {policy.policy_id}")
            return True
            
        except Exception as e:
            raise CyRISNetworkError(
                f"Failed to apply network policy {policy.policy_id}: {e}",
                operation="apply_network_policy",
                range_id=policy.range_id
            ) from e
    
    def remove_network_policy(self, range_id: str) -> bool:
        """
        Remove network policy for a range.
        
        Args:
            range_id: Range identifier
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Removing Layer 3 network policy for range {range_id}")
        
        try:
            firewall_policy_name = f"cyris-layer3-{range_id}"
            firewall_policy_id = f"policy-{range_id}-{firewall_policy_name}"
            return self.firewall_manager.remove_policy(firewall_policy_id)
        except Exception as e:
            self.logger.error(f"Failed to remove network policy for range {range_id}: {e}")
            return False
    
    def _parse_forwarding_rule(self, rule_spec: str) -> Optional[NetworkRule]:
        """
        Parse a single forwarding rule specification.
        
        Supports formats like:
        - "src=internal dst=dmz dport=80,443"
        - "src=office dst=servers sport=1024-65535 dport=25,53"
        
        Args:
            rule_spec: Rule specification string
            
        Returns:
            NetworkRule object or None if parsing fails
        """
        try:
            # Parse rule components
            rule_parts = rule_spec.split()
            src_networks = []
            dst_networks = []
            sports = []
            dports = []
            protocol = "tcp"  # default
            
            for part in rule_parts:
                if part.startswith('src='):
                    src_networks = part.split('=')[1].split(',')
                elif part.startswith('dst='):
                    dst_networks = part.split('=')[1].split(',')
                elif part.startswith('sport='):
                    sports = part.split('=')[1].split(',')
                elif part.startswith('dport='):
                    dports = part.split('=')[1].split(',')
                elif part.startswith('proto='):
                    protocol = part.split('=')[1]
            
            if not src_networks or not dst_networks:
                self.logger.warning(f"Invalid rule specification - missing src/dst: {rule_spec}")
                return None
            
            return NetworkRule(
                source_networks=src_networks,
                destination_networks=dst_networks,
                ports=dports,
                source_ports=sports,
                protocol=protocol
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse forwarding rule '{rule_spec}': {e}")
            return None
    
    def _generate_iptables_rules(self, policy: NetworkPolicy) -> List[str]:
        """
        Generate iptables FORWARD rules from network policy.
        
        Creates rules in the style of the legacy system:
        - Stateful connection tracking (NEW,ESTABLISHED,RELATED)
        - Port-specific rules when ports are specified
        - Bidirectional communication support
        
        Args:
            policy: NetworkPolicy with parsed rules
            
        Returns:
            List of iptables command strings
        """
        iptables_rules = []
        
        # Process each network rule
        for rule in policy.rules:
            for src_network in rule.source_networks:
                for dst_network in rule.destination_networks:
                    
                    # Resolve network names to CIDR blocks
                    src_cidr = self._resolve_network_cidr(src_network, policy.ip_mappings)
                    dst_cidr = self._resolve_network_cidr(dst_network, policy.ip_mappings)
                    
                    # Generate rules for each port combination
                    if rule.ports:
                        for port in rule.ports:
                            iptables_rule = self._build_iptables_rule(
                                src_cidr, dst_cidr, rule.protocol, port, rule.source_ports
                            )
                            iptables_rules.append(iptables_rule)
                    else:
                        # No specific ports - allow all for the protocol
                        iptables_rule = self._build_iptables_rule(
                            src_cidr, dst_cidr, rule.protocol, None, rule.source_ports
                        )
                        iptables_rules.append(iptables_rule)
        
        # Add bidirectional state tracking rule (legacy compatibility)
        if iptables_rules:
            iptables_rules.append(
                "iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT"
            )
        
        return iptables_rules
    
    def _resolve_network_cidr(self, network_name: str, ip_mappings: Dict[str, str]) -> str:
        """
        Resolve network name to CIDR notation.
        
        Args:
            network_name: Network name from YAML
            ip_mappings: Network name to CIDR mappings
            
        Returns:
            CIDR string (e.g., "192.168.1.0/24")
        """
        # Check if it's already a CIDR
        try:
            ipaddress.ip_network(network_name, strict=False)
            return network_name
        except ValueError:
            pass
        
        # Look up in mappings
        if network_name in ip_mappings:
            return ip_mappings[network_name]
        
        # Default fallback (allows all traffic - should be avoided in production)
        self.logger.warning(f"Could not resolve network '{network_name}', using 0.0.0.0/0")
        return "0.0.0.0/0"
    
    def _build_iptables_rule(
        self, 
        src_cidr: str, 
        dst_cidr: str, 
        protocol: str,
        port: Optional[str] = None,
        source_ports: Optional[List[str]] = None
    ) -> str:
        """
        Build individual iptables FORWARD rule.
        
        Creates rules in legacy system format with stateful tracking.
        
        Args:
            src_cidr: Source CIDR block
            dst_cidr: Destination CIDR block
            protocol: Protocol (tcp/udp/icmp/all)
            port: Destination port (optional)
            source_ports: Source ports (optional)
            
        Returns:
            Complete iptables command string
        """
        # Base rule with stateful tracking
        rule_parts = [
            "iptables -A FORWARD",
            "-m state",
            f"-s {src_cidr}",
            f"-d {dst_cidr}"
        ]
        
        # Add protocol specification
        if protocol.lower() != "all":
            rule_parts.append(f"-p {protocol}")
        
        # Add port specifications
        if port and protocol.lower() in ['tcp', 'udp']:
            rule_parts.append(f"--dport {port}")
        
        if source_ports and protocol.lower() in ['tcp', 'udp']:
            sport_str = ','.join(source_ports)
            rule_parts.append(f"--sport {sport_str}")
        
        # Add state tracking and action
        rule_parts.extend([
            "--state NEW,ESTABLISHED,RELATED",
            "-j ACCEPT"
        ])
        
        return ' '.join(rule_parts)
    
    def _parse_iptables_rule(self, rule: str) -> Dict[str, Any]:
        """
        Parse iptables rule string to extract components for FirewallManager.
        
        Args:
            rule: iptables command string
            
        Returns:
            Dictionary with rule components
        """
        # Basic parsing to extract key components
        components = {}
        
        # Extract source
        src_match = re.search(r'-s\s+([^\s]+)', rule)
        if src_match:
            components['source_ip'] = src_match.group(1)
        
        # Extract destination  
        dst_match = re.search(r'-d\s+([^\s]+)', rule)
        if dst_match:
            components['dest_ip'] = dst_match.group(1)
        
        # Extract protocol
        proto_match = re.search(r'-p\s+([^\s]+)', rule)
        if proto_match:
            from ..infrastructure.network.firewall_manager import RuleProtocol
            # Map to RuleProtocol enum
            protocol_str = proto_match.group(1).lower()
            protocol_map = {
                'tcp': RuleProtocol.TCP,
                'udp': RuleProtocol.UDP,
                'icmp': RuleProtocol.ICMP,
                'all': RuleProtocol.ALL
            }
            components['protocol'] = protocol_map.get(protocol_str, RuleProtocol.ALL)
        
        # Extract destination port
        dport_match = re.search(r'--dport\s+([^\s]+)', rule)
        if dport_match:
            try:
                components['dest_port'] = int(dport_match.group(1))
            except ValueError:
                # Handle port ranges or complex port specs by taking first port
                port_spec = dport_match.group(1)
                if '-' in port_spec:
                    components['dest_port'] = int(port_spec.split('-')[0])
                elif ',' in port_spec:
                    components['dest_port'] = int(port_spec.split(',')[0])
                else:
                    # Skip invalid port specs
                    pass
        
        # Set direction to FORWARD for Layer 3 rules
        components['direction'] = "FORWARD"
        
        # Add comment
        components['comment'] = f"Layer 3 automation rule"
        
        return components
    
    def get_policy_status(self, range_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for a range's network policy.
        
        Args:
            range_id: Range identifier
            
        Returns:
            Policy status dictionary or None if not found
        """
        try:
            firewall_policy_name = f"cyris-layer3-{range_id}"
            firewall_policy_id = f"policy-{range_id}-{firewall_policy_name}"
            
            # Get policy from firewall manager
            policy_info = self.firewall_manager.get_policy(firewall_policy_id)
            
            if policy_info:
                return {
                    'range_id': range_id,
                    'policy_id': firewall_policy_id,
                    'active': True,
                    'policy_info': {
                        'name': policy_info.name,
                        'description': policy_info.description,
                        'rule_count': len(policy_info.custom_rules),
                        'created_at': policy_info.created_at
                    }
                }
            else:
                return {
                    'range_id': range_id,
                    'policy_id': firewall_policy_id,
                    'active': False,
                    'policy_info': None
                }
            
        except Exception as e:
            self.logger.error(f"Failed to get policy status for range {range_id}: {e}")
            return None
    
    def validate_topology_config(self, topology_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate topology configuration for Layer 3 rules.
        
        Args:
            topology_config: Topology configuration to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check if forwarding_rules exist
        if 'forwarding_rules' not in topology_config:
            return True, []  # No rules to validate
        
        forwarding_rules = topology_config['forwarding_rules']
        if not isinstance(forwarding_rules, list):
            errors.append("forwarding_rules must be a list")
            return False, errors
        
        # Validate each rule
        for i, rule_spec in enumerate(forwarding_rules):
            if 'rule' not in rule_spec:
                errors.append(f"Rule {i+1}: missing 'rule' specification")
                continue
            
            rule_str = rule_spec['rule']
            try:
                parsed_rule = self._parse_forwarding_rule(rule_str)
                if not parsed_rule:
                    errors.append(f"Rule {i+1}: failed to parse '{rule_str}'")
            except Exception as e:
                errors.append(f"Rule {i+1}: validation error - {e}")
        
        return len(errors) == 0, errors