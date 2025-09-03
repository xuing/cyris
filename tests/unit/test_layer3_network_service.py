"""
Unit Tests for Layer3NetworkService

Tests the Layer 3 network automation service without external dependencies,
using mocks for FirewallManager and TopologyManager integration.
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from src.cyris.services.layer3_network_service import Layer3NetworkService
from src.cyris.domain.entities.network_policy import NetworkRule, NetworkPolicy
from src.cyris.core.exceptions import CyRISNetworkError


class TestLayer3NetworkService:
    """Unit tests for Layer3NetworkService"""
    
    @pytest.fixture
    def mock_firewall_manager(self):
        """Mock FirewallManager for testing"""
        mock_fm = Mock()
        mock_fm.initialize_firewall.return_value = None
        mock_fm.create_network_policy.return_value = "test-policy-id"
        mock_fm.add_custom_rule.return_value = "test-rule-id"
        mock_fm.apply_policy.return_value = True
        mock_fm.remove_policy.return_value = True
        mock_fm.get_policy_status.return_value = {"status": "active", "rules": 3}
        return mock_fm
    
    @pytest.fixture
    def mock_topology_manager(self):
        """Mock TopologyManager for testing"""
        mock_tm = Mock()
        mock_tm.networks = {
            'office': {'cidr': '192.168.100.0/24'},
            'servers': {'cidr': '192.168.200.0/24'},
            'dmz': {'cidr': '192.168.50.0/24'}
        }
        return mock_tm
    
    @pytest.fixture
    def layer3_service(self, mock_firewall_manager, mock_topology_manager):
        """Create Layer3NetworkService instance with mocked dependencies"""
        return Layer3NetworkService(
            firewall_manager=mock_firewall_manager,
            topology_manager=mock_topology_manager,
            logger=logging.getLogger("test")
        )
    
    @pytest.fixture
    def sample_topology_config(self):
        """Sample topology configuration for testing"""
        return {
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80,443'},
                {'rule': 'src=office dst=dmz dport=25 proto=tcp'},
                {'rule': 'src=servers dst=office sport=1024-65535 dport=53 proto=udp'}
            ]
        }
    
    @pytest.fixture
    def sample_network_info(self):
        """Sample network information for testing"""
        return {
            'office': {
                'cidr': '192.168.100.0/24',
                'gateway': '192.168.100.1',
                'full_name': 'cyris-test-office'
            },
            'servers': {
                'cidr': '192.168.200.0/24', 
                'gateway': '192.168.200.1',
                'full_name': 'cyris-test-servers'
            },
            'dmz': {
                'cidr': '192.168.50.0/24',
                'gateway': '192.168.50.1',
                'full_name': 'cyris-test-dmz'
            }
        }
    
    def test_initialization_with_defaults(self):
        """Test service initialization with default parameters"""
        service = Layer3NetworkService()
        
        assert service.firewall_manager is not None
        assert service.topology_manager is None
        assert service.logger is not None
    
    def test_initialization_with_custom_components(self, mock_firewall_manager, mock_topology_manager):
        """Test service initialization with custom components"""
        custom_logger = logging.getLogger("custom")
        service = Layer3NetworkService(
            firewall_manager=mock_firewall_manager,
            topology_manager=mock_topology_manager,
            logger=custom_logger
        )
        
        assert service.firewall_manager == mock_firewall_manager
        assert service.topology_manager == mock_topology_manager
        assert service.logger == custom_logger
    
    def test_firewall_initialization_warning(self):
        """Test firewall initialization warning handling"""
        mock_fm = Mock()
        mock_fm.initialize_firewall.side_effect = Exception("Connection failed")
        
        # Should not raise exception, just log warning
        service = Layer3NetworkService(firewall_manager=mock_fm)
        assert service.firewall_manager == mock_fm
    
    def test_parse_forwarding_rule_basic(self, layer3_service):
        """Test basic forwarding rule parsing"""
        rule = layer3_service._parse_forwarding_rule("src=office dst=servers dport=80")
        
        assert rule is not None
        assert rule.source_networks == ['office']
        assert rule.destination_networks == ['servers']
        assert rule.ports == ['80']
        assert rule.protocol == 'tcp'
    
    def test_parse_forwarding_rule_complex(self, layer3_service):
        """Test complex forwarding rule parsing with multiple parameters"""
        rule = layer3_service._parse_forwarding_rule(
            "src=office,dmz dst=servers sport=1024-65535 dport=80,443,8080 proto=tcp"
        )
        
        assert rule is not None
        assert rule.source_networks == ['office', 'dmz']
        assert rule.destination_networks == ['servers']
        assert rule.source_ports == ['1024-65535']
        assert rule.ports == ['80', '443', '8080']
        assert rule.protocol == 'tcp'
    
    def test_parse_forwarding_rule_udp_protocol(self, layer3_service):
        """Test UDP protocol rule parsing"""
        rule = layer3_service._parse_forwarding_rule("src=office dst=servers dport=53 proto=udp")
        
        assert rule is not None
        assert rule.protocol == 'udp'
        assert rule.ports == ['53']
    
    def test_parse_forwarding_rule_invalid_missing_src(self, layer3_service):
        """Test invalid rule parsing - missing source"""
        rule = layer3_service._parse_forwarding_rule("dst=servers dport=80")
        
        assert rule is None
    
    def test_parse_forwarding_rule_invalid_missing_dst(self, layer3_service):
        """Test invalid rule parsing - missing destination"""
        rule = layer3_service._parse_forwarding_rule("src=office dport=80")
        
        assert rule is None
    
    def test_parse_forwarding_rule_invalid_protocol(self, layer3_service):
        """Test invalid protocol handling"""
        with pytest.raises(ValueError, match="Unsupported protocol"):
            NetworkRule(
                source_networks=['office'],
                destination_networks=['servers'],
                protocol='invalid'
            )
    
    def test_resolve_network_cidr_direct(self, layer3_service):
        """Test network CIDR resolution with direct CIDR input"""
        cidr = layer3_service._resolve_network_cidr("192.168.100.0/24", {})
        assert cidr == "192.168.100.0/24"
    
    def test_resolve_network_cidr_mapping(self, layer3_service):
        """Test network CIDR resolution using mappings"""
        mappings = {'office': '192.168.100.0/24', 'servers': '192.168.200.0/24'}
        
        office_cidr = layer3_service._resolve_network_cidr("office", mappings)
        assert office_cidr == "192.168.100.0/24"
        
        servers_cidr = layer3_service._resolve_network_cidr("servers", mappings)
        assert servers_cidr == "192.168.200.0/24"
    
    def test_resolve_network_cidr_fallback(self, layer3_service):
        """Test network CIDR resolution with fallback to 0.0.0.0/0"""
        cidr = layer3_service._resolve_network_cidr("unknown_network", {})
        assert cidr == "0.0.0.0/0"
    
    def test_build_iptables_rule_basic(self, layer3_service):
        """Test basic iptables rule building"""
        rule = layer3_service._build_iptables_rule(
            "192.168.100.0/24", 
            "192.168.200.0/24", 
            "tcp", 
            "80"
        )
        
        assert "iptables -A FORWARD" in rule
        assert "-s 192.168.100.0/24" in rule
        assert "-d 192.168.200.0/24" in rule
        assert "-p tcp" in rule
        assert "--dport 80" in rule
        assert "--state NEW,ESTABLISHED,RELATED" in rule
        assert "-j ACCEPT" in rule
    
    def test_build_iptables_rule_with_source_ports(self, layer3_service):
        """Test iptables rule building with source ports"""
        rule = layer3_service._build_iptables_rule(
            "192.168.100.0/24", 
            "192.168.200.0/24", 
            "tcp", 
            "80",
            source_ports=["1024", "2048"]
        )
        
        assert "--sport 1024,2048" in rule
        assert "--dport 80" in rule
    
    def test_build_iptables_rule_protocol_all(self, layer3_service):
        """Test iptables rule building with protocol 'all'"""
        rule = layer3_service._build_iptables_rule(
            "192.168.100.0/24", 
            "192.168.200.0/24", 
            "all"
        )
        
        assert "-p tcp" not in rule
        assert "-p udp" not in rule
        assert "192.168.100.0/24" in rule
        assert "192.168.200.0/24" in rule
    
    def test_build_iptables_rule_udp_protocol(self, layer3_service):
        """Test iptables rule building with UDP protocol"""
        rule = layer3_service._build_iptables_rule(
            "192.168.100.0/24", 
            "192.168.200.0/24", 
            "udp", 
            "53"
        )
        
        assert "-p udp" in rule
        assert "--dport 53" in rule
    
    def test_generate_iptables_rules_single_rule(self, layer3_service):
        """Test iptables rules generation for single network rule"""
        policy = NetworkPolicy(policy_id="test", range_id="test")
        policy.add_rule(NetworkRule(
            source_networks=['office'],
            destination_networks=['servers'],
            ports=['80'],
            protocol='tcp'
        ))
        policy.ip_mappings = {
            'office': '192.168.100.0/24',
            'servers': '192.168.200.0/24'
        }
        
        rules = layer3_service._generate_iptables_rules(policy)
        
        # Should generate rule + stateful tracking rule
        assert len(rules) >= 2
        assert any("192.168.100.0/24" in rule and "192.168.200.0/24" in rule for rule in rules)
        assert any("RELATED,ESTABLISHED" in rule for rule in rules)
    
    def test_generate_iptables_rules_multiple_ports(self, layer3_service):
        """Test iptables rules generation for multiple ports"""
        policy = NetworkPolicy(policy_id="test", range_id="test")
        policy.add_rule(NetworkRule(
            source_networks=['office'],
            destination_networks=['servers'],
            ports=['80', '443'],
            protocol='tcp'
        ))
        policy.ip_mappings = {
            'office': '192.168.100.0/24',
            'servers': '192.168.200.0/24'
        }
        
        rules = layer3_service._generate_iptables_rules(policy)
        
        # Should generate separate rule for each port
        port_80_rules = [rule for rule in rules if "--dport 80" in rule]
        port_443_rules = [rule for rule in rules if "--dport 443" in rule]
        
        assert len(port_80_rules) == 1
        assert len(port_443_rules) == 1
    
    def test_generate_iptables_rules_multiple_networks(self, layer3_service):
        """Test iptables rules generation for multiple source/destination networks"""
        policy = NetworkPolicy(policy_id="test", range_id="test")
        policy.add_rule(NetworkRule(
            source_networks=['office', 'dmz'],
            destination_networks=['servers'],
            ports=['80'],
            protocol='tcp'
        ))
        policy.ip_mappings = {
            'office': '192.168.100.0/24',
            'dmz': '192.168.50.0/24',
            'servers': '192.168.200.0/24'
        }
        
        rules = layer3_service._generate_iptables_rules(policy)
        
        # Should generate rule for each network combination
        office_rules = [rule for rule in rules if "192.168.100.0/24" in rule and "192.168.200.0/24" in rule]
        dmz_rules = [rule for rule in rules if "192.168.50.0/24" in rule and "192.168.200.0/24" in rule]
        
        assert len(office_rules) >= 1
        assert len(dmz_rules) >= 1
    
    def test_process_topology_rules_success(self, layer3_service, sample_topology_config, sample_network_info):
        """Test successful topology rules processing"""
        range_id = "test_range_123"
        
        policy = layer3_service.process_topology_rules(
            topology_config=sample_topology_config,
            range_id=range_id,
            network_info=sample_network_info
        )
        
        assert policy.range_id == range_id
        assert policy.policy_id == f"layer3-{range_id}"
        assert len(policy.rules) == 3  # Three rules from sample config
        assert len(policy.iptables_rules) > 0
        assert 'office' in policy.ip_mappings
        assert 'servers' in policy.ip_mappings
        assert 'dmz' in policy.ip_mappings
    
    def test_process_topology_rules_empty_rules(self, layer3_service):
        """Test topology processing with no forwarding rules"""
        topology_config = {}
        range_id = "test_range_empty"
        
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id=range_id
        )
        
        assert policy.range_id == range_id
        assert len(policy.rules) == 0
        assert len(policy.iptables_rules) == 0
    
    def test_process_topology_rules_invalid_rule(self, layer3_service):
        """Test topology processing with invalid rule specification"""
        topology_config = {
            'forwarding_rules': [
                {'rule': 'invalid_rule_format'},
                {'rule': 'src=office dst=servers dport=80'}  # valid rule
            ]
        }
        range_id = "test_range_mixed"
        
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id=range_id
        )
        
        # Should process valid rule and skip invalid one
        assert len(policy.rules) == 1
        assert policy.rules[0].source_networks == ['office']
    
    def test_process_topology_rules_exception_handling(self, layer3_service):
        """Test exception handling during topology processing"""
        # Force an exception during rule generation
        layer3_service._parse_forwarding_rule = Mock(side_effect=Exception("Parse error"))
        
        topology_config = {
            'forwarding_rules': [{'rule': 'src=office dst=servers'}]
        }
        
        with pytest.raises(CyRISNetworkError, match="Failed to process topology rules"):
            layer3_service.process_topology_rules(
                topology_config=topology_config,
                range_id="test_range_error"
            )
    
    def test_apply_network_policy_success(self, layer3_service, mock_firewall_manager):
        """Test successful network policy application"""
        policy = NetworkPolicy(policy_id="test-policy", range_id="test_range")
        policy.add_rule(NetworkRule(
            source_networks=['office'],
            destination_networks=['servers'],
            ports=['80']
        ))
        policy.iptables_rules = ["iptables -A FORWARD -s 192.168.100.0/24 -d 192.168.200.0/24 -j ACCEPT"]
        
        result = layer3_service.apply_network_policy(policy)
        
        assert result is True
        mock_firewall_manager.create_network_policy.assert_called_once()
        mock_firewall_manager.add_custom_rule.assert_called()
        mock_firewall_manager.apply_policy.assert_called_once()
    
    def test_apply_network_policy_failure(self, layer3_service, mock_firewall_manager):
        """Test network policy application failure"""
        mock_firewall_manager.apply_policy.return_value = False
        
        policy = NetworkPolicy(policy_id="test-policy", range_id="test_range")
        policy.add_rule(NetworkRule(
            source_networks=['office'],
            destination_networks=['servers']
        ))
        
        result = layer3_service.apply_network_policy(policy)
        
        assert result is False
    
    def test_apply_network_policy_exception(self, layer3_service, mock_firewall_manager):
        """Test network policy application with exception"""
        mock_firewall_manager.create_network_policy.side_effect = Exception("Firewall error")
        
        policy = NetworkPolicy(policy_id="test-policy", range_id="test_range")
        
        with pytest.raises(CyRISNetworkError, match="Failed to apply network policy"):
            layer3_service.apply_network_policy(policy)
    
    def test_remove_network_policy_success(self, layer3_service, mock_firewall_manager):
        """Test successful network policy removal"""
        mock_firewall_manager.remove_policy.return_value = True
        
        result = layer3_service.remove_network_policy("test_range")
        
        assert result is True
        mock_firewall_manager.remove_policy.assert_called_once_with("cyris-layer3-test_range")
    
    def test_remove_network_policy_failure(self, layer3_service, mock_firewall_manager):
        """Test network policy removal failure"""
        mock_firewall_manager.remove_policy.return_value = False
        
        result = layer3_service.remove_network_policy("test_range")
        
        assert result is False
    
    def test_remove_network_policy_exception(self, layer3_service, mock_firewall_manager):
        """Test network policy removal with exception"""
        mock_firewall_manager.remove_policy.side_effect = Exception("Remove error")
        
        result = layer3_service.remove_network_policy("test_range")
        
        assert result is False
    
    def test_get_policy_status_success(self, layer3_service, mock_firewall_manager):
        """Test successful policy status retrieval"""
        mock_policy_info = {"status": "active", "rules": 5}
        mock_firewall_manager.get_policy_status.return_value = mock_policy_info
        
        result = layer3_service.get_policy_status("test_range")
        
        assert result is not None
        assert result['range_id'] == "test_range"
        assert result['policy_id'] == "cyris-layer3-test_range"
        assert result['active'] is True
        assert result['policy_info'] == mock_policy_info
    
    def test_get_policy_status_not_found(self, layer3_service, mock_firewall_manager):
        """Test policy status retrieval when policy not found"""
        mock_firewall_manager.get_policy_status.return_value = None
        
        result = layer3_service.get_policy_status("nonexistent_range")
        
        assert result is not None
        assert result['active'] is False
        assert result['policy_info'] is None
    
    def test_get_policy_status_exception(self, layer3_service, mock_firewall_manager):
        """Test policy status retrieval with exception"""
        mock_firewall_manager.get_policy_status.side_effect = Exception("Status error")
        
        result = layer3_service.get_policy_status("test_range")
        
        assert result is None
    
    def test_validate_topology_config_valid(self, layer3_service, sample_topology_config):
        """Test topology configuration validation with valid config"""
        is_valid, errors = layer3_service.validate_topology_config(sample_topology_config)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_topology_config_no_rules(self, layer3_service):
        """Test topology configuration validation with no forwarding rules"""
        config = {'networks': [{'name': 'office'}]}
        
        is_valid, errors = layer3_service.validate_topology_config(config)
        
        assert is_valid is True  # No rules is valid
        assert len(errors) == 0
    
    def test_validate_topology_config_invalid_format(self, layer3_service):
        """Test topology configuration validation with invalid format"""
        config = {
            'forwarding_rules': "not_a_list"  # Should be a list
        }
        
        is_valid, errors = layer3_service.validate_topology_config(config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert "must be a list" in errors[0]
    
    def test_validate_topology_config_missing_rule_spec(self, layer3_service):
        """Test topology configuration validation with missing rule specification"""
        config = {
            'forwarding_rules': [
                {'invalid': 'no_rule_key'},
                {'rule': 'src=office dst=servers'}  # valid
            ]
        }
        
        is_valid, errors = layer3_service.validate_topology_config(config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert "missing 'rule' specification" in errors[0]
    
    def test_parse_iptables_rule_components(self, layer3_service):
        """Test parsing iptables rule components for FirewallManager"""
        rule = "iptables -A FORWARD -s 192.168.100.0/24 -d 192.168.200.0/24 -p tcp --dport 80 -j ACCEPT"
        
        components = layer3_service._parse_iptables_rule(rule)
        
        assert components['source_ip'] == '192.168.100.0/24'
        assert components['destination_ip'] == '192.168.200.0/24'
        assert components['protocol'] == 'tcp'
        assert components['destination_port'] == '80'
    
    def test_parse_iptables_rule_minimal(self, layer3_service):
        """Test parsing minimal iptables rule"""
        rule = "iptables -A FORWARD -j ACCEPT"
        
        components = layer3_service._parse_iptables_rule(rule)
        
        # Should have empty components for minimal rule
        assert 'source_ip' not in components
        assert 'destination_ip' not in components
        assert 'protocol' not in components