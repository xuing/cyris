"""
Network Policy Domain Entities

This module defines the data models for Layer 3 network policies and rules,
providing type-safe structures for network automation and firewall management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import ipaddress


class NetworkProtocol(Enum):
    """Supported network protocols"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ALL = "all"


class RuleAction(Enum):
    """Firewall rule actions"""
    ACCEPT = "ACCEPT"
    DROP = "DROP"
    REJECT = "REJECT"
    LOG = "LOG"


class RuleDirection(Enum):
    """Rule traffic direction"""
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    FORWARD = "FORWARD"


@dataclass
class NetworkRule:
    """
    Individual network forwarding rule specification.
    
    Represents a single firewall rule with source/destination networks,
    ports, protocol, and action. Supports validation and serialization.
    """
    source_networks: List[str]
    destination_networks: List[str]
    ports: List[str] = field(default_factory=list)
    source_ports: List[str] = field(default_factory=list)
    protocol: str = "tcp"
    action: str = "ACCEPT"
    direction: str = "FORWARD"
    state_tracking: bool = True
    comment: Optional[str] = None
    
    def __post_init__(self):
        """Validate rule specification"""
        if not self.source_networks or not self.destination_networks:
            raise ValueError("Both source and destination networks must be specified")
        
        # Validate protocol
        if self.protocol.lower() not in ['tcp', 'udp', 'icmp', 'all']:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
        
        # Validate action
        if self.action.upper() not in ['ACCEPT', 'DROP', 'REJECT', 'LOG']:
            raise ValueError(f"Invalid action: {self.action}")
        
        # Validate direction
        if self.direction.upper() not in ['INPUT', 'OUTPUT', 'FORWARD']:
            raise ValueError(f"Invalid direction: {self.direction}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary representation"""
        return {
            'source_networks': self.source_networks,
            'destination_networks': self.destination_networks,
            'ports': self.ports,
            'source_ports': self.source_ports,
            'protocol': self.protocol,
            'action': self.action,
            'direction': self.direction,
            'state_tracking': self.state_tracking,
            'comment': self.comment
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkRule':
        """Create rule from dictionary representation"""
        return cls(
            source_networks=data.get('source_networks', []),
            destination_networks=data.get('destination_networks', []),
            ports=data.get('ports', []),
            source_ports=data.get('source_ports', []),
            protocol=data.get('protocol', 'tcp'),
            action=data.get('action', 'ACCEPT'),
            direction=data.get('direction', 'FORWARD'),
            state_tracking=data.get('state_tracking', True),
            comment=data.get('comment')
        )
    
    def validate_networks(self) -> List[str]:
        """
        Validate network specifications are valid CIDR blocks or network names.
        
        Returns:
            List of validation errors, empty if all valid
        """
        errors = []
        
        for network_list, name in [(self.source_networks, 'source'), 
                                   (self.destination_networks, 'destination')]:
            for network in network_list:
                # Skip if it's a network name (will be resolved later)
                if not any(c in network for c in ['/', '.']):
                    continue
                
                # Try to parse as CIDR
                try:
                    ipaddress.ip_network(network, strict=False)
                except ValueError:
                    errors.append(f"Invalid {name} network: {network}")
        
        return errors
    
    def validate_ports(self) -> List[str]:
        """
        Validate port specifications.
        
        Returns:
            List of validation errors, empty if all valid
        """
        errors = []
        
        for port_list, name in [(self.ports, 'destination'), 
                                (self.source_ports, 'source')]:
            for port_spec in port_list:
                # Handle port ranges (e.g., "1024-65535")
                if '-' in port_spec:
                    try:
                        start, end = port_spec.split('-')
                        start_port = int(start)
                        end_port = int(end)
                        if not (1 <= start_port <= 65535) or not (1 <= end_port <= 65535):
                            errors.append(f"Invalid {name} port range: {port_spec}")
                        if start_port > end_port:
                            errors.append(f"Invalid {name} port range order: {port_spec}")
                    except (ValueError, AttributeError):
                        errors.append(f"Invalid {name} port range format: {port_spec}")
                else:
                    # Single port
                    try:
                        port_num = int(port_spec)
                        if not (1 <= port_num <= 65535):
                            errors.append(f"Invalid {name} port: {port_spec}")
                    except ValueError:
                        errors.append(f"Invalid {name} port format: {port_spec}")
        
        return errors


@dataclass
class NetworkPolicy:
    """
    Complete network policy for a cyber range.
    
    Contains all network rules and IP mappings for a range,
    along with generated iptables commands and metadata.
    """
    policy_id: str
    range_id: str
    rules: List[NetworkRule] = field(default_factory=list)
    ip_mappings: Dict[str, str] = field(default_factory=dict)  # network_name -> CIDR
    iptables_rules: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    applied: bool = False
    description: Optional[str] = None
    
    def add_rule(self, rule: NetworkRule) -> None:
        """
        Add a rule to this policy.
        
        Args:
            rule: NetworkRule to add
        """
        self.rules.append(rule)
        self.modified_at = datetime.now()
    
    def remove_rule(self, index: int) -> Optional[NetworkRule]:
        """
        Remove a rule by index.
        
        Args:
            index: Rule index to remove
            
        Returns:
            Removed rule or None if index invalid
        """
        if 0 <= index < len(self.rules):
            rule = self.rules.pop(index)
            self.modified_at = datetime.now()
            return rule
        return None
    
    def get_rule_count(self) -> int:
        """Get total number of rules in this policy"""
        return len(self.rules)
    
    def get_iptables_count(self) -> int:
        """Get total number of generated iptables rules"""
        return len(self.iptables_rules)
    
    def add_ip_mapping(self, network_name: str, cidr: str) -> None:
        """
        Add or update network name to CIDR mapping.
        
        Args:
            network_name: Network name
            cidr: CIDR block (e.g., "192.168.100.0/24")
        """
        # Validate CIDR
        try:
            ipaddress.ip_network(cidr, strict=False)
            self.ip_mappings[network_name] = cidr
            self.modified_at = datetime.now()
        except ValueError as e:
            raise ValueError(f"Invalid CIDR for network {network_name}: {e}")
    
    def resolve_network(self, network_name: str) -> Optional[str]:
        """
        Resolve network name to CIDR.
        
        Args:
            network_name: Network name to resolve
            
        Returns:
            CIDR string or None if not found
        """
        return self.ip_mappings.get(network_name)
    
    def validate(self) -> List[str]:
        """
        Validate the entire policy.
        
        Returns:
            List of validation errors, empty if valid
        """
        errors = []
        
        # Validate each rule
        for i, rule in enumerate(self.rules):
            rule_errors = rule.validate_networks()
            if rule_errors:
                errors.extend([f"Rule {i+1}: {e}" for e in rule_errors])
            
            port_errors = rule.validate_ports()
            if port_errors:
                errors.extend([f"Rule {i+1}: {e}" for e in port_errors])
        
        # Check for unresolved network names
        all_networks = set()
        for rule in self.rules:
            all_networks.update(rule.source_networks)
            all_networks.update(rule.destination_networks)
        
        for network in all_networks:
            # Skip CIDR blocks
            if '/' in network or network == "0.0.0.0/0":
                continue
            # Check if network name can be resolved
            if network not in self.ip_mappings:
                errors.append(f"Unresolved network name: {network}")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary representation"""
        return {
            'policy_id': self.policy_id,
            'range_id': self.range_id,
            'rules': [rule.to_dict() for rule in self.rules],
            'ip_mappings': self.ip_mappings,
            'iptables_rules': self.iptables_rules,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'applied': self.applied,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkPolicy':
        """Create policy from dictionary representation"""
        policy = cls(
            policy_id=data['policy_id'],
            range_id=data['range_id'],
            ip_mappings=data.get('ip_mappings', {}),
            iptables_rules=data.get('iptables_rules', []),
            applied=data.get('applied', False),
            description=data.get('description')
        )
        
        # Add rules
        for rule_data in data.get('rules', []):
            policy.add_rule(NetworkRule.from_dict(rule_data))
        
        # Parse timestamps
        if 'created_at' in data:
            policy.created_at = datetime.fromisoformat(data['created_at'])
        if 'modified_at' in data:
            policy.modified_at = datetime.fromisoformat(data['modified_at'])
        
        return policy
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get policy statistics.
        
        Returns:
            Dictionary with policy statistics
        """
        total_source_networks = set()
        total_dest_networks = set()
        total_ports = set()
        protocols = set()
        
        for rule in self.rules:
            total_source_networks.update(rule.source_networks)
            total_dest_networks.update(rule.destination_networks)
            total_ports.update(rule.ports)
            protocols.add(rule.protocol)
        
        return {
            'total_rules': len(self.rules),
            'total_iptables_rules': len(self.iptables_rules),
            'unique_source_networks': len(total_source_networks),
            'unique_dest_networks': len(total_dest_networks),
            'unique_ports': len(total_ports),
            'protocols_used': list(protocols),
            'ip_mappings_count': len(self.ip_mappings),
            'policy_applied': self.applied,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat()
        }


@dataclass
class NetworkPolicyValidationResult:
    """
    Result of network policy validation.
    
    Contains validation status and detailed error/warning messages.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def add_error(self, error: str) -> None:
        """Add an error message"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message"""
        self.warnings.append(warning)
    
    def add_suggestion(self, suggestion: str) -> None:
        """Add a suggestion message"""
        self.suggestions.append(suggestion)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'suggestions': self.suggestions,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }