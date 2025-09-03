"""
Integration Tests for Layer 3 Network Service

Tests the Layer3NetworkService integration with FirewallManager and TopologyManager,
using real components but controlled test environments.
"""

import pytest
import tempfile
import ipaddress
import json
from pathlib import Path
from unittest.mock import patch, Mock
import logging

from src.cyris.services.layer3_network_service import Layer3NetworkService
from src.cyris.infrastructure.network.firewall_manager import FirewallManager
from src.cyris.infrastructure.network.topology_manager import NetworkTopologyManager
from src.cyris.domain.entities.network_policy import NetworkRule, NetworkPolicy
from src.cyris.core.exceptions import CyRISNetworkError


class TestLayer3NetworkIntegration:
    """Integration tests for Layer 3 network service"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for firewall configurations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture 
    def mock_subprocess_run(self):
        """Mock subprocess.run for iptables commands"""
        with patch('subprocess.run') as mock_run:
            # Mock successful iptables execution
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Chain CYRIS_FORWARD (0 references)\n"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            yield mock_run
    
    @pytest.fixture
    def firewall_manager(self, temp_config_dir, mock_subprocess_run):
        """Create FirewallManager instance for testing"""
        return FirewallManager(
            config_dir=temp_config_dir,
            logger=logging.getLogger("test_firewall")
        )
    
    @pytest.fixture
    def topology_manager(self):
        """Create NetworkTopologyManager instance for testing"""
        # Mock libvirt connection to avoid real libvirt dependency
        mock_libvirt = Mock()
        mock_libvirt.networkLookupByName.side_effect = Exception("Not found")
        return NetworkTopologyManager(libvirt_connection=mock_libvirt)
    
    @pytest.fixture
    def layer3_service(self, firewall_manager, topology_manager):
        """Create Layer3NetworkService with real components"""
        return Layer3NetworkService(
            firewall_manager=firewall_manager,
            topology_manager=topology_manager,
            logger=logging.getLogger("test_layer3")
        )
    
    @pytest.fixture
    def sample_topology_config(self):
        """Complex topology configuration for integration testing"""
        return {
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
                {'rule': 'src=office dst=servers dport=80,443'},
                {'rule': 'src=office dst=dmz dport=25 proto=tcp'},
                {'rule': 'src=servers dst=office sport=1024-65535 dport=53 proto=udp'},
                {'rule': 'src=dmz dst=servers dport=3306 proto=tcp'}
            ]
        }
    
    @pytest.fixture
    def sample_network_info(self):
        """Network information mapping for testing"""
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
    
    def test_end_to_end_policy_creation_and_application(
        self, 
        layer3_service, 
        sample_topology_config, 
        sample_network_info,
        mock_subprocess_run
    ):
        """Test complete end-to-end policy creation and application"""
        range_id = "integration_test_123"
        
        # Step 1: Process topology rules
        network_policy = layer3_service.process_topology_rules(
            topology_config=sample_topology_config,
            range_id=range_id,
            network_info=sample_network_info
        )
        
        # Verify policy was created correctly
        assert network_policy.policy_id == f"layer3-{range_id}"
        assert network_policy.range_id == range_id
        assert len(network_policy.rules) == 4  # Four forwarding rules
        assert len(network_policy.iptables_rules) > 0
        
        # Verify network mappings
        assert 'office' in network_policy.ip_mappings
        assert 'servers' in network_policy.ip_mappings
        assert 'dmz' in network_policy.ip_mappings
        assert network_policy.ip_mappings['office'] == '192.168.100.0/24'
        
        # Step 2: Apply the network policy
        success = layer3_service.apply_network_policy(network_policy)
        assert success is True
        
        # Verify firewall manager calls were made
        assert mock_subprocess_run.call_count > 0
        
        # Step 3: Verify policy status
        status = layer3_service.get_policy_status(range_id)
        assert status is not None
        assert status['range_id'] == range_id
        assert status['policy_id'] == f"policy-{range_id}-cyris-layer3-{range_id}"
    
    def test_complex_rule_generation_with_multiple_ports(
        self, 
        layer3_service, 
        sample_network_info
    ):
        """Test complex rule generation with multiple ports and protocols"""
        topology_config = {
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80,443,8080,8443'},
                {'rule': 'src=office dst=dmz dport=25,587,993 proto=tcp'}
            ]
        }
        
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id="complex_rules_test",
            network_info=sample_network_info
        )
        
        # Should generate separate iptables rule for each port
        assert len(policy.rules) == 2
        assert len(policy.iptables_rules) >= 7  # 4 ports + 3 ports + state tracking
        
        # Verify individual port rules exist
        port_80_rules = [rule for rule in policy.iptables_rules if "--dport 80" in rule]
        port_443_rules = [rule for rule in policy.iptables_rules if "--dport 443" in rule]
        port_25_rules = [rule for rule in policy.iptables_rules if "--dport 25" in rule]
        
        assert len(port_80_rules) == 1
        assert len(port_443_rules) == 1
        assert len(port_25_rules) == 1
    
    def test_network_name_resolution_with_fallbacks(self, layer3_service):
        """Test network name resolution with various scenarios"""
        topology_config = {
            'forwarding_rules': [
                {'rule': 'src=known_network dst=192.168.100.0/24 dport=80'},
                {'rule': 'src=unknown_network dst=servers dport=443'},
                {'rule': 'src=192.168.50.0/24 dst=another_unknown dport=25'}
            ]
        }
        
        network_info = {
            'known_network': {'cidr': '192.168.200.0/24'}
            # 'unknown_network' and 'another_unknown' not provided
        }
        
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id="fallback_test", 
            network_info=network_info
        )
        
        assert len(policy.rules) == 3
        assert len(policy.iptables_rules) > 0
        
        # Check that known networks are resolved correctly
        known_rules = [rule for rule in policy.iptables_rules if "192.168.200.0/24" in rule]
        assert len(known_rules) >= 1
        
        # Check that unknown networks fall back to 0.0.0.0/0
        fallback_rules = [rule for rule in policy.iptables_rules if "0.0.0.0/0" in rule]
        assert len(fallback_rules) >= 1
    
    def test_topology_manager_integration(self, topology_manager, mock_subprocess_run):
        """Test integration with NetworkTopologyManager"""
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
        desktop.ip_addr = "192.168.100.50"
        guests.append(desktop)
        
        webserver = (GuestBuilder()
                     .with_guest_id("webserver")
                     .with_basevm_host("host_1")
                     .with_basevm_config_file("/tmp/test.xml")
                     .with_basevm_type(BaseVMType.KVM)
                     .with_basevm_os_type(OSType.UBUNTU)
                     .build())
        webserver.ip_addr = "192.168.200.51"
        guests.append(webserver)
        
        # Create topology with Layer 3 integration
        topology_config = {
            'networks': [
                {'name': 'office', 'members': ['desktop.eth0']},
                {'name': 'servers', 'members': ['webserver.eth0']}
            ],
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80,443'}
            ]
        }
        
        range_id = "topology_integration_test"
        
        # This should trigger the Layer3NetworkService integration
        ip_assignments = topology_manager.create_topology(
            topology_config, guests, range_id
        )
        
        # Verify topology was created
        assert len(ip_assignments) == 2
        assert 'desktop' in ip_assignments
        assert 'webserver' in ip_assignments
        
        # Verify Layer 3 rules were applied (check that subprocess was called)
        assert mock_subprocess_run.call_count > 0
        
        # Verify forwarding rules were generated
        assert hasattr(topology_manager, 'forwarding_rules')
        assert len(topology_manager.forwarding_rules) > 0
    
    def test_policy_cleanup_and_removal(
        self, 
        layer3_service, 
        sample_topology_config, 
        sample_network_info,
        mock_subprocess_run
    ):
        """Test policy creation followed by cleanup"""
        range_id = "cleanup_test_456"
        
        # Create and apply policy
        policy = layer3_service.process_topology_rules(
            topology_config=sample_topology_config,
            range_id=range_id,
            network_info=sample_network_info
        )
        
        success = layer3_service.apply_network_policy(policy)
        assert success is True
        
        # Verify policy exists
        status = layer3_service.get_policy_status(range_id)
        assert status is not None
        assert status['active'] is True
        
        # Remove the policy
        removal_success = layer3_service.remove_network_policy(range_id)
        assert removal_success is True
        
        # Verify policy is removed (in a real implementation, this would check firewall state)
        # For mocked tests, we verify the firewall manager was called
        assert mock_subprocess_run.call_count > 0
    
    def test_error_handling_with_invalid_firewall_config(
        self, 
        temp_config_dir, 
        topology_manager
    ):
        """Test error handling when firewall operations fail"""
        
        # Create a firewall manager that will fail
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1  # Failure
            mock_result.stderr = "iptables: command failed"
            mock_run.return_value = mock_result
            
            firewall_manager = FirewallManager(
                config_dir=temp_config_dir,
                logger=logging.getLogger("test_error_firewall")
            )
            
            layer3_service = Layer3NetworkService(
                firewall_manager=firewall_manager,
                topology_manager=topology_manager,
                logger=logging.getLogger("test_error_layer3")
            )
            
            # This should handle firewall initialization gracefully
            assert layer3_service.firewall_manager is not None
            
            # Attempt to process rules (should not crash)
            topology_config = {
                'forwarding_rules': [
                    {'rule': 'src=office dst=servers dport=80'}
                ]
            }
            
            try:
                policy = layer3_service.process_topology_rules(
                    topology_config=topology_config,
                    range_id="error_test"
                )
                # Should succeed in creating policy
                assert policy is not None
                
                # Application might fail due to iptables error, but should be handled gracefully
                result = layer3_service.apply_network_policy(policy)
                # Result depends on firewall manager error handling
                
            except Exception as e:
                # Should be a CyRISNetworkError with meaningful message
                assert isinstance(e, CyRISNetworkError)
    
    def test_concurrent_policy_operations(
        self, 
        layer3_service, 
        sample_network_info,
        mock_subprocess_run
    ):
        """Test handling multiple concurrent policy operations"""
        import threading
        
        results = {}
        errors = {}
        
        def create_and_apply_policy(range_suffix):
            try:
                topology_config = {
                    'forwarding_rules': [
                        {'rule': f'src=office dst=servers dport={8000 + range_suffix}'}
                    ]
                }
                
                policy = layer3_service.process_topology_rules(
                    topology_config=topology_config,
                    range_id=f"concurrent_test_{range_suffix}",
                    network_info=sample_network_info
                )
                
                success = layer3_service.apply_network_policy(policy)
                results[range_suffix] = success
                
            except Exception as e:
                errors[range_suffix] = str(e)
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_and_apply_policy, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)
        
        # Check results
        assert len(results) == 3
        assert len(errors) == 0
        
        for i in range(3):
            assert results[i] is True
    
    def test_rule_validation_and_error_reporting(self, layer3_service):
        """Test comprehensive rule validation and error reporting"""
        
        # Test with various invalid configurations
        invalid_configs = [
            # Missing forwarding_rules key entirely - should be valid (no rules)
            {},
            
            # Invalid forwarding_rules format
            {'forwarding_rules': 'not_a_list'},
            
            # Missing rule specifications
            {'forwarding_rules': [{'invalid': 'no_rule_key'}]},
            
            # Mixed valid and invalid rules
            {
                'forwarding_rules': [
                    {'rule': 'invalid_format'},
                    {'rule': 'src=office dst=servers dport=80'},  # valid
                    {'invalid_key': 'no_rule'}
                ]
            }
        ]
        
        for i, config in enumerate(invalid_configs):
            if i == 0:  # Empty config should be valid
                is_valid, errors = layer3_service.validate_topology_config(config)
                assert is_valid is True
                assert len(errors) == 0
            else:  # Other configs should have validation errors
                is_valid, errors = layer3_service.validate_topology_config(config)
                assert is_valid is False
                assert len(errors) > 0
                
                # Errors should be descriptive
                for error in errors:
                    assert isinstance(error, str)
                    assert len(error) > 10  # Should have meaningful description
    
    def test_stateful_connection_tracking(self, layer3_service, sample_network_info):
        """Test that generated rules include proper stateful connection tracking"""
        topology_config = {
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80,443'},
            ]
        }
        
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id="stateful_test",
            network_info=sample_network_info
        )
        
        # Verify stateful tracking rules are generated
        stateful_rules = [rule for rule in policy.iptables_rules 
                         if "NEW,ESTABLISHED,RELATED" in rule]
        
        # Should have stateful rules for each port + one general stateful rule
        assert len(stateful_rules) >= 2  # At least 2 port rules
        
        # Verify the general stateful connection rule is present
        general_stateful = [rule for rule in policy.iptables_rules 
                           if "RELATED,ESTABLISHED" in rule and "dport" not in rule]
        assert len(general_stateful) >= 1
    
    def test_protocol_specific_rule_generation(self, layer3_service, sample_network_info):
        """Test generation of protocol-specific rules"""
        topology_config = {
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80 proto=tcp'},
                {'rule': 'src=office dst=servers dport=53 proto=udp'},
                {'rule': 'src=office dst=servers proto=icmp'}
            ]
        }
        
        policy = layer3_service.process_topology_rules(
            topology_config=topology_config,
            range_id="protocol_test",
            network_info=sample_network_info
        )
        
        # Verify TCP rule
        tcp_rules = [rule for rule in policy.iptables_rules if "-p tcp" in rule and "--dport 80" in rule]
        assert len(tcp_rules) == 1
        
        # Verify UDP rule
        udp_rules = [rule for rule in policy.iptables_rules if "-p udp" in rule and "--dport 53" in rule]
        assert len(udp_rules) == 1
        
        # Verify ICMP rule
        icmp_rules = [rule for rule in policy.iptables_rules if "-p icmp" in rule]
        assert len(icmp_rules) == 1


class TestLayer3ServiceFailureScenarios:
    """Test failure scenarios and edge cases"""
    
    def test_firewall_manager_unavailable(self):
        """Test behavior when FirewallManager is unavailable"""
        # Create service without firewall manager
        service = Layer3NetworkService(firewall_manager=None)
        
        # Should initialize with default firewall manager
        assert service.firewall_manager is not None
    
    def test_topology_manager_unavailable(self):
        """Test behavior when TopologyManager is unavailable"""
        service = Layer3NetworkService(topology_manager=None)
        
        # Should handle missing topology manager gracefully
        assert service.topology_manager is None
        
        # Should still be able to process rules without network info
        topology_config = {
            'forwarding_rules': [
                {'rule': 'src=192.168.1.0/24 dst=192.168.2.0/24 dport=80'}
            ]
        }
        
        policy = service.process_topology_rules(
            topology_config=topology_config,
            range_id="no_topology_test"
        )
        
        assert policy is not None
        assert len(policy.rules) == 1
    
    @patch('subprocess.run')
    def test_iptables_command_failure(self, mock_run):
        """Test handling of iptables command failures"""
        # Mock iptables failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "iptables: Chain already exists"
        mock_run.return_value = mock_result
        
        with tempfile.TemporaryDirectory() as temp_dir:
            firewall_manager = FirewallManager(config_dir=Path(temp_dir))
            service = Layer3NetworkService(firewall_manager=firewall_manager)
            
            # Should handle iptables failures gracefully during initialization
            assert service.firewall_manager is not None


if __name__ == "__main__":
    # Enable detailed logging for manual testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    pytest.main([__file__, "-v", "-s"])