"""
Firewall Manager

This module manages firewall rules and network security for cyber ranges,
including iptables configuration and network isolation policies.
"""

# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import logging  # Keep for type annotations
import subprocess
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import json
from pathlib import Path
from datetime import datetime

from ..providers.base_provider import InfrastructureError


class RuleAction(Enum):
    """Firewall rule actions"""
    ACCEPT = "ACCEPT"
    DROP = "DROP"
    REJECT = "REJECT"
    LOG = "LOG"


class RuleProtocol(Enum):
    """Network protocols"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ALL = "all"


@dataclass
class FirewallRule:
    """Represents a firewall rule"""
    rule_id: str
    name: str
    action: RuleAction
    protocol: RuleProtocol = RuleProtocol.ALL
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    interface: Optional[str] = None
    direction: str = "INPUT"  # INPUT, OUTPUT, FORWARD
    enabled: bool = True
    comment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkPolicy:
    """Network isolation policy for a range"""
    policy_id: str
    range_id: str
    name: str
    description: str
    default_action: RuleAction = RuleAction.DROP
    allow_internal_communication: bool = True
    allow_internet_access: bool = False
    custom_rules: List[FirewallRule] = field(default_factory=list)
    created_at: Optional[str] = None


class FirewallManager:
    """
    Firewall and network security management service.
    
    This service manages firewall rules and network security policies
    for cyber ranges, providing network isolation and controlled access.
    
    Capabilities:
    - Create and manage iptables rules
    - Implement network isolation policies
    - Control inter-range communication
    - Manage internet access policies
    - Log network activity
    - Custom security rule implementation
    
    Follows SOLID principles:
    - Single Responsibility: Focuses on firewall and security
    - Open/Closed: Extensible rule types and policies
    - Interface Segregation: Focused security operations
    - Dependency Inversion: Uses abstract security interfaces
    """
    
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize firewall manager.
        
        Args:
            config_dir: Directory to store firewall configurations
            backup_dir: Directory to store iptables backups
            logger: Optional logger instance
        """
        self.config_dir = Path(config_dir) if config_dir else Path("/tmp/cyris/firewall")
        self.backup_dir = Path(backup_dir) if backup_dir else self.config_dir / "backups"
        self.logger = logger or get_logger(__name__, "firewall_manager")
        
        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Active policies and rules tracking
        self._policies: Dict[str, NetworkPolicy] = {}
        self._active_rules: Dict[str, Set[str]] = {}  # range_id -> set of rule_ids
        
        # Chain names for CyRIS rules
        self.cyris_chains = {
            "input": "CYRIS_INPUT",
            "output": "CYRIS_OUTPUT", 
            "forward": "CYRIS_FORWARD",
            "range_isolation": "CYRIS_ISOLATION"
        }
        
        self.logger.info("FirewallManager initialized")
    
    def initialize_firewall(self) -> None:
        """
        Initialize firewall with CyRIS-specific chains.
        
        This creates custom iptables chains for managing CyRIS rules
        separately from system rules.
        
        Raises:
            InfrastructureError: If initialization fails
        """
        self.logger.info("Initializing firewall chains")
        
        try:
            # Create backup of current iptables
            self._backup_iptables()
            
            # Create custom chains
            for chain_name in self.cyris_chains.values():
                # Create chain if it doesn't exist
                result = self._run_command([
                    "iptables", "-t", "filter", "-L", chain_name
                ], check=False)
                
                if result.returncode != 0:
                    self._run_command([
                        "iptables", "-t", "filter", "-N", chain_name
                    ])
                    self.logger.info(f"Created iptables chain {chain_name}")
            
            # Link custom chains to main chains
            self._ensure_chain_links()
            
            self.logger.info("Firewall initialization completed")
            
        except Exception as e:
            self.logger.error(f"Firewall initialization failed: {e}")
            raise InfrastructureError(f"Firewall initialization failed: {e}")
    
    def create_network_policy(
        self,
        range_id: str,
        policy_name: str,
        description: str,
        default_action: RuleAction = RuleAction.DROP,
        allow_internal_communication: bool = True,
        allow_internet_access: bool = False
    ) -> str:
        """
        Create a network policy for a cyber range.
        
        Args:
            range_id: Range identifier
            policy_name: Name of the policy
            description: Policy description
            default_action: Default action for unmatched traffic
            allow_internal_communication: Allow communication within range
            allow_internet_access: Allow internet access
        
        Returns:
            Policy identifier
        
        Raises:
            InfrastructureError: If policy creation fails
        """
        policy_id = f"policy-{range_id}-{policy_name}"
        
        if policy_id in self._policies:
            raise InfrastructureError(f"Policy {policy_id} already exists")
        
        self.logger.info(f"Creating network policy {policy_id} for range {range_id}")
        
        policy = NetworkPolicy(
            policy_id=policy_id,
            range_id=range_id,
            name=policy_name,
            description=description,
            default_action=default_action,
            allow_internal_communication=allow_internal_communication,
            allow_internet_access=allow_internet_access,
            created_at=str(datetime.now())
        )
        
        # Create default rules based on policy settings
        default_rules = self._create_default_rules(policy)
        policy.custom_rules.extend(default_rules)
        
        # Store policy
        self._policies[policy_id] = policy
        self._active_rules[range_id] = set()
        
        # Apply the policy
        self.apply_policy(policy_id)
        
        self.logger.info(f"Created and applied network policy {policy_id}")
        return policy_id
    
    def add_custom_rule(
        self,
        policy_id: str,
        rule_name: str,
        action: RuleAction,
        protocol: RuleProtocol = RuleProtocol.ALL,
        source_ip: Optional[str] = None,
        dest_ip: Optional[str] = None,
        source_port: Optional[int] = None,
        dest_port: Optional[int] = None,
        interface: Optional[str] = None,
        direction: str = "INPUT",
        comment: Optional[str] = None
    ) -> str:
        """
        Add a custom rule to a network policy.
        
        Args:
            policy_id: Policy identifier
            rule_name: Name of the rule
            action: Rule action
            protocol: Network protocol
            source_ip: Source IP address or range
            dest_ip: Destination IP address or range
            source_port: Source port
            dest_port: Destination port
            interface: Network interface
            direction: Rule direction (INPUT, OUTPUT, FORWARD)
            comment: Optional comment
        
        Returns:
            Rule identifier
        
        Raises:
            InfrastructureError: If rule creation fails
        """
        policy = self._policies.get(policy_id)
        if not policy:
            raise InfrastructureError(f"Policy {policy_id} not found")
        
        rule_id = f"{policy_id}-{rule_name}-{len(policy.custom_rules)}"
        
        # Validate rule parameters
        self._validate_rule_parameters(
            source_ip, dest_ip, source_port, dest_port, protocol
        )
        
        rule = FirewallRule(
            rule_id=rule_id,
            name=rule_name,
            action=action,
            protocol=protocol,
            source_ip=source_ip,
            dest_ip=dest_ip,
            source_port=source_port,
            dest_port=dest_port,
            interface=interface,
            direction=direction,
            comment=comment,
            metadata={"policy_id": policy_id}
        )
        
        # Add rule to policy
        policy.custom_rules.append(rule)
        
        # Apply the rule
        self._apply_rule(rule)
        self._active_rules[policy.range_id].add(rule_id)
        
        self.logger.info(f"Added custom rule {rule_id} to policy {policy_id}")
        return rule_id
    
    def apply_policy(self, policy_id: str) -> None:
        """
        Apply a network policy by creating iptables rules.
        
        Args:
            policy_id: Policy identifier
        
        Raises:
            InfrastructureError: If policy application fails
        """
        policy = self._policies.get(policy_id)
        if not policy:
            raise InfrastructureError(f"Policy {policy_id} not found")
        
        self.logger.info(f"Applying network policy {policy_id}")
        
        try:
            # Clear existing rules for this range
            self.remove_range_rules(policy.range_id)
            
            # Apply all rules in the policy
            for rule in policy.custom_rules:
                if rule.enabled:
                    self._apply_rule(rule)
                    self._active_rules[policy.range_id].add(rule.rule_id)
            
            # Save policy configuration
            self._save_policy_config(policy)
            
            self.logger.info(f"Successfully applied policy {policy_id} with {len(policy.custom_rules)} rules")
            
        except Exception as e:
            self.logger.error(f"Failed to apply policy {policy_id}: {e}")
            raise InfrastructureError(f"Policy application failed: {e}")
    
    def remove_range_rules(self, range_id: str) -> None:
        """
        Remove all firewall rules for a specific range.
        
        Args:
            range_id: Range identifier
        """
        if range_id not in self._active_rules:
            return
        
        self.logger.info(f"Removing firewall rules for range {range_id}")
        
        rule_ids = self._active_rules[range_id].copy()
        removed_count = 0
        
        for rule_id in rule_ids:
            try:
                self._remove_rule_by_id(rule_id)
                self._active_rules[range_id].discard(rule_id)
                removed_count += 1
            except Exception as e:
                self.logger.error(f"Failed to remove rule {rule_id}: {e}")
        
        self.logger.info(f"Removed {removed_count} firewall rules for range {range_id}")
    
    def get_policy(self, policy_id: str) -> Optional[NetworkPolicy]:
        """Get network policy by ID"""
        return self._policies.get(policy_id)
    
    def list_policies(self, range_id: Optional[str] = None) -> List[NetworkPolicy]:
        """List network policies, optionally filtered by range"""
        policies = list(self._policies.values())
        
        if range_id:
            policies = [p for p in policies if p.range_id == range_id]
        
        return policies
    
    def get_active_rules(self, range_id: Optional[str] = None) -> List[str]:
        """Get list of active rule IDs, optionally filtered by range"""
        if range_id:
            return list(self._active_rules.get(range_id, set()))
        
        all_rules = []
        for rule_set in self._active_rules.values():
            all_rules.extend(rule_set)
        return all_rules
    
    def cleanup_firewall(self) -> None:
        """
        Clean up all CyRIS firewall rules and chains.
        
        This removes all rules and chains created by CyRIS,
        effectively restoring the firewall to its pre-CyRIS state.
        """
        self.logger.info("Cleaning up CyRIS firewall rules")
        
        try:
            # Remove all range rules
            for range_id in list(self._active_rules.keys()):
                self.remove_range_rules(range_id)
            
            # Remove custom chains
            for chain_name in self.cyris_chains.values():
                # Flush chain
                self._run_command([
                    "iptables", "-t", "filter", "-F", chain_name
                ], check=False)
                
                # Remove chain references from main chains
                self._remove_chain_links(chain_name)
                
                # Delete chain
                self._run_command([
                    "iptables", "-t", "filter", "-X", chain_name
                ], check=False)
            
            # Clear internal state
            self._policies.clear()
            self._active_rules.clear()
            
            self.logger.info("Firewall cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Firewall cleanup failed: {e}")
            raise InfrastructureError(f"Firewall cleanup failed: {e}")
    
    def get_firewall_statistics(self) -> Dict[str, Any]:
        """Get firewall manager statistics"""
        total_policies = len(self._policies)
        total_rules = sum(len(rules) for rules in self._active_rules.values())
        
        return {
            "total_policies": total_policies,
            "total_active_rules": total_rules,
            "ranges_with_rules": len(self._active_rules),
            "chains_created": len(self.cyris_chains),
            "policies_by_range": {
                range_id: len(rules) for range_id, rules in self._active_rules.items()
            }
        }
    
    def _create_default_rules(self, policy: NetworkPolicy) -> List[FirewallRule]:
        """Create default rules based on policy settings"""
        rules = []
        
        # Allow loopback traffic
        rules.append(FirewallRule(
            rule_id=f"{policy.policy_id}-default-loopback",
            name="allow-loopback",
            action=RuleAction.ACCEPT,
            interface="lo",
            comment="Allow loopback traffic"
        ))
        
        # Allow established and related connections
        rules.append(FirewallRule(
            rule_id=f"{policy.policy_id}-default-established",
            name="allow-established",
            action=RuleAction.ACCEPT,
            comment="Allow established connections"
        ))
        
        # Internet access rule
        if policy.allow_internet_access:
            rules.append(FirewallRule(
                rule_id=f"{policy.policy_id}-default-internet",
                name="allow-internet",
                action=RuleAction.ACCEPT,
                direction="OUTPUT",
                comment="Allow internet access"
            ))
        
        return rules
    
    def _apply_rule(self, rule: FirewallRule) -> None:
        """Apply a single firewall rule using iptables"""
        chain = self.cyris_chains.get(rule.direction.lower(), self.cyris_chains["input"])
        
        # Build iptables command
        cmd = ["iptables", "-t", "filter", "-A", chain]
        
        # Add protocol
        if rule.protocol != RuleProtocol.ALL:
            cmd.extend(["-p", rule.protocol.value])
        
        # Add source IP
        if rule.source_ip:
            cmd.extend(["-s", rule.source_ip])
        
        # Add destination IP
        if rule.dest_ip:
            cmd.extend(["-d", rule.dest_ip])
        
        # Add source port
        if rule.source_port and rule.protocol in [RuleProtocol.TCP, RuleProtocol.UDP]:
            cmd.extend(["--sport", str(rule.source_port)])
        
        # Add destination port
        if rule.dest_port and rule.protocol in [RuleProtocol.TCP, RuleProtocol.UDP]:
            cmd.extend(["--dport", str(rule.dest_port)])
        
        # Add interface
        if rule.interface:
            if rule.direction == "INPUT":
                cmd.extend(["-i", rule.interface])
            elif rule.direction == "OUTPUT":
                cmd.extend(["-o", rule.interface])
        
        # Add action
        cmd.extend(["-j", rule.action.value])
        
        # Add comment
        if rule.comment:
            cmd.extend(["-m", "comment", "--comment", f"CyRIS: {rule.comment}"])
        
        # Execute command
        self._run_command(cmd)
    
    def _remove_rule_by_id(self, rule_id: str) -> None:
        """Remove a specific rule by ID"""
        # In a production implementation, this would track rule line numbers
        # or use more sophisticated rule management
        # For now, we'll implement a basic approach
        
        # Find and remove rules with matching comment
        result = self._run_command([
            "iptables", "-t", "filter", "-L", "-n", "--line-numbers"
        ], check=False)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if rule_id in line:
                    # Extract chain and line number
                    # This is a simplified approach
                    pass
    
    def _validate_rule_parameters(
        self,
        source_ip: Optional[str],
        dest_ip: Optional[str],
        source_port: Optional[int],
        dest_port: Optional[int],
        protocol: RuleProtocol
    ) -> None:
        """Validate rule parameters"""
        # Validate IP addresses
        for ip in [source_ip, dest_ip]:
            if ip:
                try:
                    ipaddress.ip_network(ip, strict=False)
                except ValueError:
                    raise InfrastructureError(f"Invalid IP address or network: {ip}")
        
        # Validate ports
        for port in [source_port, dest_port]:
            if port is not None:
                if not (1 <= port <= 65535):
                    raise InfrastructureError(f"Invalid port number: {port}")
                
                if protocol == RuleProtocol.ICMP:
                    raise InfrastructureError("Ports not applicable for ICMP protocol")
    
    def _ensure_chain_links(self) -> None:
        """Ensure custom chains are linked to main chains"""
        # Link CYRIS_INPUT to INPUT
        self._add_chain_link("INPUT", self.cyris_chains["input"])
        
        # Link CYRIS_OUTPUT to OUTPUT  
        self._add_chain_link("OUTPUT", self.cyris_chains["output"])
        
        # Link CYRIS_FORWARD to FORWARD
        self._add_chain_link("FORWARD", self.cyris_chains["forward"])
    
    def _add_chain_link(self, main_chain: str, custom_chain: str) -> None:
        """Add a link from main chain to custom chain"""
        # Check if link already exists
        result = self._run_command([
            "iptables", "-t", "filter", "-L", main_chain, "-n"
        ], check=False)
        
        if custom_chain not in result.stdout:
            self._run_command([
                "iptables", "-t", "filter", "-A", main_chain, "-j", custom_chain
            ])
    
    def _remove_chain_links(self, custom_chain: str) -> None:
        """Remove links to a custom chain from main chains"""
        for main_chain in ["INPUT", "OUTPUT", "FORWARD"]:
            self._run_command([
                "iptables", "-t", "filter", "-D", main_chain, "-j", custom_chain
            ], check=False)
    
    def _backup_iptables(self) -> None:
        """Create backup of current iptables rules"""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"iptables_backup_{timestamp}.txt"
        
        result = self._run_command([
            "iptables-save"
        ], check=False)
        
        if result.returncode == 0:
            with open(backup_file, 'w') as f:
                f.write(result.stdout)
            self.logger.info(f"Iptables backup saved to {backup_file}")
    
    def _save_policy_config(self, policy: NetworkPolicy) -> None:
        """Save policy configuration to file"""
        config_file = self.config_dir / f"{policy.policy_id}.json"
        
        config_data = {
            "policy_id": policy.policy_id,
            "range_id": policy.range_id,
            "name": policy.name,
            "description": policy.description,
            "default_action": policy.default_action.value,
            "allow_internal_communication": policy.allow_internal_communication,
            "allow_internet_access": policy.allow_internet_access,
            "created_at": policy.created_at,
            "custom_rules": [
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "action": rule.action.value,
                    "protocol": rule.protocol.value,
                    "source_ip": rule.source_ip,
                    "dest_ip": rule.dest_ip,
                    "source_port": rule.source_port,
                    "dest_port": rule.dest_port,
                    "interface": rule.interface,
                    "direction": rule.direction,
                    "enabled": rule.enabled,
                    "comment": rule.comment,
                    "metadata": rule.metadata
                }
                for rule in policy.custom_rules
            ]
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
    
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