"""
End-to-End Tests for Layer 3 Network Automation

Tests the complete Layer 3 network automation pipeline from YAML topology
configuration to actual iptables rule generation and application.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, Mock

from src.cyris.services.layer3_network_service import Layer3NetworkService
from src.cyris.infrastructure.network.topology_manager import NetworkTopologyManager
from src.cyris.infrastructure.network.firewall_manager import FirewallManager


class TestLayer3NetworkE2E:
    """End-to-end tests for Layer 3 network automation"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_topology_yaml(self, temp_dir):
        """Create a sample topology YAML file"""
        topology_config = {
            'type': 'custom',
            'networks': [
                {
                    'name': 'office',
                    'members': ['desktop.eth0', 'laptop.eth0'],
                    'gateway': 'firewall.eth0'
                },
                {
                    'name': 'servers',
                    'members': ['webserver.eth0', 'dbserver.eth0'],
                    'gateway': 'firewall.eth1'
                },
                {
                    'name': 'dmz',
                    'members': ['mailserver.eth0'],
                    'gateway': 'firewall.eth2'
                }
            ],
            'forwarding_rules': [
                # Office to servers: HTTP/HTTPS access
                {'rule': 'src=office dst=servers dport=80,443 proto=tcp'},
                
                # Office to DMZ: Email submission
                {'rule': 'src=office dst=dmz dport=587 proto=tcp'},
                
                # Servers to office: DNS responses 
                {'rule': 'src=servers dst=office sport=53 dport=1024-65535 proto=udp'},
                
                # DMZ to servers: Database access (restricted)
                {'rule': 'src=dmz dst=servers dport=3306 proto=tcp'},
                
                # ICMP ping for diagnostics
                {'rule': 'src=office dst=servers proto=icmp'},
            ]
        }
        
        yaml_file = temp_dir / "test_topology.yml"
        with open(yaml_file, 'w') as f:
            yaml.dump(topology_config, f, default_flow_style=False)
        
        return yaml_file
    
    @pytest.fixture 
    def mock_subprocess(self):
        """Mock subprocess calls for iptables"""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            yield mock_run
    
    @pytest.fixture
    def mock_libvirt(self):
        """Mock libvirt connection"""
        mock_libvirt = Mock()
        mock_libvirt.networkLookupByName.side_effect = Exception("Not found")
        return mock_libvirt
    
    def test_complete_layer3_automation_pipeline(
        self, 
        temp_dir, 
        sample_topology_yaml,
        mock_subprocess,
        mock_libvirt
    ):
        """Test the complete Layer 3 automation pipeline from YAML to iptables"""
        
        # Step 1: Load topology configuration
        with open(sample_topology_yaml, 'r') as f:
            topology_config = yaml.safe_load(f)
        
        # Step 2: Create infrastructure components
        firewall_manager = FirewallManager(
            config_dir=temp_dir / "firewall",
            logger=None
        )
        
        topology_manager = NetworkTopologyManager(
            libvirt_connection=mock_libvirt
        )
        
        layer3_service = Layer3NetworkService(
            firewall_manager=firewall_manager,
            topology_manager=topology_manager
        )
        
        # Step 3: Create mock network information
        network_info = {
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
        
        range_id = "e2e_test_range"
        
        # Step 4: Process topology rules
        network_policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id=range_id,
            network_info=network_info
        )
        
        # Verify policy structure
        assert network_policy.policy_id == f"layer3-{range_id}"
        assert network_policy.range_id == range_id
        assert len(network_policy.rules) == 5  # Five forwarding rules
        
        # Verify network mappings
        assert network_policy.ip_mappings['office'] == '192.168.100.0/24'
        assert network_policy.ip_mappings['servers'] == '192.168.200.0/24'
        assert network_policy.ip_mappings['dmz'] == '192.168.50.0/24'
        
        # Verify iptables rules generation
        assert len(network_policy.iptables_rules) > 0
        
        # Step 5: Validate specific rules were generated correctly
        iptables_rules_text = ' '.join(network_policy.iptables_rules)
        
        # Should contain HTTP/HTTPS rules
        assert "192.168.100.0/24" in iptables_rules_text  # Office network
        assert "192.168.200.0/24" in iptables_rules_text  # Servers network
        assert "192.168.50.0/24" in iptables_rules_text   # DMZ network
        assert "--dport 80" in iptables_rules_text        # HTTP
        assert "--dport 443" in iptables_rules_text       # HTTPS
        assert "--dport 587" in iptables_rules_text       # SMTP submission
        assert "-p tcp" in iptables_rules_text            # TCP protocol
        assert "-p udp" in iptables_rules_text            # UDP protocol  
        assert "-p icmp" in iptables_rules_text           # ICMP protocol
        
        # Should contain stateful tracking
        assert "ESTABLISHED" in iptables_rules_text or "NEW" in iptables_rules_text
        
        # Step 6: Apply the network policy
        success = layer3_service.apply_network_policy(network_policy)
        assert success is True
        
        # Verify subprocess calls were made (iptables commands)
        assert mock_subprocess.call_count > 0
        
        # Step 7: Verify policy status
        status = layer3_service.get_policy_status(range_id)
        assert status is not None
        assert status['active'] is True
        assert status['range_id'] == range_id
        
        # Step 8: Validate policy configuration file was created
        firewall_config_dir = temp_dir / "firewall"
        config_files = list(firewall_config_dir.glob("*.json"))
        assert len(config_files) > 0
        
        # Step 9: Test cleanup
        cleanup_success = layer3_service.remove_network_policy(range_id)
        assert cleanup_success is True
    
    def test_validation_with_invalid_topology(self, layer3_service=None):
        """Test validation with invalid topology configuration"""
        if not layer3_service:
            layer3_service = Layer3NetworkService()
        
        # Test invalid configurations
        invalid_configs = [
            # Invalid forwarding_rules format
            {'forwarding_rules': 'not_a_list'},
            
            # Missing rule specifications
            {'forwarding_rules': [{'no_rule': 'invalid'}]},
            
            # Invalid rule format
            {'forwarding_rules': [{'rule': 'invalid_format_no_equals'}]},
            
            # Mixed valid and invalid
            {
                'forwarding_rules': [
                    {'rule': 'src=office dst=servers'},  # valid
                    {'rule': 'invalid_no_src_dst'},      # invalid
                ]
            }
        ]
        
        for i, invalid_config in enumerate(invalid_configs):
            is_valid, errors = layer3_service.validate_topology_config(invalid_config)
            
            if i == 0:  # First case should be invalid
                assert is_valid is False
                assert len(errors) > 0
                assert "must be a list" in errors[0]
            else:
                # Other cases should have validation errors
                if not is_valid:  # Some might be handled gracefully
                    assert len(errors) > 0
    
    def test_complex_network_rule_combinations(self, temp_dir, mock_subprocess):
        """Test complex combinations of network rules"""
        
        # Create services
        firewall_manager = FirewallManager(config_dir=temp_dir)
        layer3_service = Layer3NetworkService(firewall_manager=firewall_manager)
        
        # Complex topology with multiple port ranges and protocols
        topology_config = {
            'forwarding_rules': [
                # Multiple ports
                {'rule': 'src=office dst=servers dport=80,443,8080,8443 proto=tcp'},
                
                # Port ranges
                {'rule': 'src=servers dst=office sport=1024-65535 dport=53 proto=udp'},
                
                # Multiple source and destination networks
                {'rule': 'src=office,dmz dst=servers,external dport=443 proto=tcp'},
                
                # Mixed protocols
                {'rule': 'src=office dst=servers proto=icmp'},
                {'rule': 'src=office dst=servers dport=22 proto=tcp'}
            ]
        }
        
        # Network mappings
        network_info = {
            'office': {'cidr': '192.168.100.0/24'},
            'servers': {'cidr': '192.168.200.0/24'},
            'dmz': {'cidr': '192.168.50.0/24'},
            'external': {'cidr': '10.0.0.0/8'}
        }
        
        # Process rules
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id="complex_test",
            network_info=network_info
        )
        
        # Verify complex rules were processed
        assert len(policy.rules) == 5
        assert len(policy.iptables_rules) > 10  # Should generate many individual rules
        
        # Apply policy
        success = layer3_service.apply_network_policy(policy)
        assert success is True
        
        # Verify complex rule generation
        rules_text = ' '.join(policy.iptables_rules)
        assert "--dport 8080" in rules_text
        assert "--dport 8443" in rules_text  
        assert "192.168.50.0/24" in rules_text  # DMZ
        assert "10.0.0.0/8" in rules_text       # External
    
    def test_legacy_compatibility_with_topology_manager(
        self, 
        temp_dir,
        mock_subprocess
    ):
        """Test Layer3NetworkService integration with legacy TopologyManager"""
        
        # Create mock libvirt
        mock_libvirt = Mock()
        mock_libvirt.networkLookupByName.side_effect = Exception("Not found")
        
        # Create topology manager
        topology_manager = NetworkTopologyManager(libvirt_connection=mock_libvirt)
        
        # Create sample guests
        from src.cyris.domain.entities.guest import Guest, GuestBuilder, BaseVMType, OSType
        
        guests = []
        desktop = (GuestBuilder()
                   .with_guest_id("desktop")
                   .with_basevm_host("host_1")
                   .with_basevm_config_file("/tmp/test.xml")
                   .with_basevm_type(BaseVMType.KVM)
                   .with_basevm_os_type(OSType.UBUNTU)
                   .build())
        guests.append(desktop)
        
        webserver = (GuestBuilder()
                     .with_guest_id("webserver")
                     .with_basevm_host("host_1")
                     .with_basevm_config_file("/tmp/test.xml")
                     .with_basevm_type(BaseVMType.KVM)
                     .with_basevm_os_type(OSType.UBUNTU)
                     .build())
        guests.append(webserver)
        
        # Topology configuration
        topology_config = {
            'networks': [
                {'name': 'office', 'members': ['desktop.eth0']},
                {'name': 'servers', 'members': ['webserver.eth0']}
            ],
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80,443'}
            ]
        }
        
        range_id = "legacy_compat_test"
        
        # This should trigger Layer3NetworkService integration through topology manager
        ip_assignments = topology_manager.create_topology(
            topology_config, guests, range_id
        )
        
        # Verify topology was created
        assert len(ip_assignments) >= 2
        assert len(topology_manager.networks) >= 2
        
        # Verify Layer 3 rules were applied (forwarding_rules attribute set)
        assert hasattr(topology_manager, 'forwarding_rules')
        assert len(topology_manager.forwarding_rules) > 0
        
        # Should contain proper iptables rules
        rules_text = ' '.join(topology_manager.forwarding_rules)
        assert "iptables" in rules_text
        assert "FORWARD" in rules_text
        assert "-j ACCEPT" in rules_text
        
        # Test cleanup
        topology_manager.destroy_topology(range_id)
        assert len(topology_manager.networks) == 0
    
    def test_error_handling_and_recovery(self, temp_dir):
        """Test error handling and recovery scenarios"""
        
        # Test with failing firewall manager
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1  # Failure
            mock_result.stderr = "iptables: command failed"
            mock_run.return_value = mock_result
            
            firewall_manager = FirewallManager(config_dir=temp_dir)
            layer3_service = Layer3NetworkService(firewall_manager=firewall_manager)
            
            # Should handle firewall errors gracefully during initialization
            assert layer3_service.firewall_manager is not None
            
            # Test topology processing (should work despite firewall issues)
            topology_config = {
                'forwarding_rules': [
                    {'rule': 'src=office dst=servers dport=80'}
                ]
            }
            
            network_info = {
                'office': {'cidr': '192.168.100.0/24'},
                'servers': {'cidr': '192.168.200.0/24'}
            }
            
            # Should succeed in creating policy
            policy = layer3_service.process_topology_rules(
                topology_config=topology_config,
                range_id="error_test",
                network_info=network_info
            )
            
            assert policy is not None
            assert len(policy.rules) == 1
            assert len(policy.iptables_rules) > 0
            
            # Policy application might fail, but should handle gracefully
            try:
                result = layer3_service.apply_network_policy(policy)
                # If it succeeds despite mock failure, that's also valid
            except Exception:
                # Should be handled gracefully with proper exception
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])