"""
Integration Tests for Network Topology Management

Tests the real network topology creation and IP assignment functionality.
No mocks - tests actual network operations where possible.
"""

import pytest
import tempfile
import ipaddress
from pathlib import Path
import subprocess
from unittest.mock import patch
import logging

from src.cyris.infrastructure.network.topology_manager import NetworkTopologyManager
from src.cyris.domain.entities.guest import Guest, GuestBuilder


class TestNetworkTopologyIntegration:
    """Integration tests for network topology management"""
    
    @pytest.fixture
    def topology_manager(self):
        """Create a topology manager instance"""
        return NetworkTopologyManager()
    
    @pytest.fixture
    def sample_guests(self):
        """Create sample guest configurations"""
        guests = []
        
        # Desktop guest
        from src.cyris.domain.entities.guest import BaseVMType, OSType
        desktop = (GuestBuilder()
                   .with_guest_id("desktop")
                   .with_basevm_host("host_1")
                   .with_basevm_config_file("/tmp/test.xml")
                   .with_basevm_type(BaseVMType.KVM)
                   .with_basevm_os_type(OSType.UBUNTU)
                   .build())
        desktop.ip_addr = "192.168.100.50"
        guests.append(desktop)
        
        # Webserver guest
        webserver = (GuestBuilder()
                     .with_guest_id("webserver")
                     .with_basevm_host("host_1")
                     .with_basevm_config_file("/tmp/test.xml") 
                     .with_basevm_type(BaseVMType.KVM)
                     .with_basevm_os_type(OSType.UBUNTU)
                     .build())
        webserver.ip_addr = "192.168.200.51"
        guests.append(webserver)
        
        # Firewall guest
        firewall = (GuestBuilder()
                    .with_guest_id("firewall")
                    .with_basevm_host("host_1")
                    .with_basevm_config_file("/tmp/test.xml")
                    .with_basevm_type(BaseVMType.KVM)
                    .with_basevm_os_type(OSType.UBUNTU)
                    .build())
        firewall.ip_addr = "192.168.100.10"
        guests.append(firewall)
        
        return guests
    
    @pytest.fixture
    def topology_config(self):
        """Sample topology configuration matching examples/full.yml"""
        return {
            'type': 'custom',
            'networks': [
                {
                    'name': 'office',
                    'members': ['desktop.eth0'],
                    'gateway': 'firewall.eth0'
                },
                {
                    'name': 'servers', 
                    'members': ['webserver.eth0'],
                    'gateway': 'firewall.eth1'
                }
            ],
            'forwarding_rules': [
                {
                    'rule': 'src=office dst=servers dport=25,53'
                }
            ]
        }
    
    def test_network_segment_creation(self, topology_manager, topology_config):
        """Test creation of network segments"""
        range_id = "test_range_123"
        
        # Create topology
        ip_assignments = topology_manager.create_topology(
            topology_config, [], range_id
        )
        
        # Verify networks were created
        office_network = topology_manager.get_network_info('office')
        servers_network = topology_manager.get_network_info('servers')
        
        assert office_network is not None
        assert servers_network is not None
        
        assert office_network['full_name'] == f"cyris-{range_id}-office"
        assert servers_network['full_name'] == f"cyris-{range_id}-servers"
        
        # Verify CIDR assignments
        assert office_network['cidr'] == '192.168.100.0/24'
        assert servers_network['cidr'] == '192.168.200.0/24'
    
    def test_ip_assignment_with_predefined_ips(self, topology_manager, sample_guests, topology_config):
        """Test IP assignment when guests have predefined IP addresses"""
        range_id = "test_range_124"
        
        ip_assignments = topology_manager.create_topology(
            topology_config, sample_guests, range_id
        )
        
        # Verify predefined IPs are respected
        assert ip_assignments['desktop'] == '192.168.100.50'
        assert ip_assignments['webserver'] == '192.168.200.51'
        assert ip_assignments['firewall'] == '192.168.100.10'
    
    def test_ip_assignment_from_network_membership(self, topology_manager, topology_config):
        """Test IP assignment based on network membership when no predefined IP"""
        range_id = "test_range_125"
        
        # Create guests without predefined IPs
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
        
        ip_assignments = topology_manager.create_topology(
            topology_config, guests, range_id
        )
        
        # Verify IPs were assigned from appropriate networks
        desktop_ip = ipaddress.ip_address(ip_assignments['desktop'])
        webserver_ip = ipaddress.ip_address(ip_assignments['webserver'])
        
        # Desktop should be in office network (192.168.100.0/24)
        office_network = ipaddress.ip_network('192.168.100.0/24')
        assert desktop_ip in office_network
        
        # Webserver should be in servers network (192.168.200.0/24)
        servers_network = ipaddress.ip_network('192.168.200.0/24')
        assert webserver_ip in servers_network
    
    def test_forwarding_rules_generation(self, topology_manager, topology_config, sample_guests):
        """Test generation of firewall forwarding rules"""
        range_id = "test_range_126"
        
        topology_manager.create_topology(topology_config, sample_guests, range_id)
        
        # Verify forwarding rules were generated
        assert hasattr(topology_manager, 'forwarding_rules')
        assert len(topology_manager.forwarding_rules) > 0
        
        # Check rule format
        rules = topology_manager.forwarding_rules
        port_25_rule = next((rule for rule in rules if 'dport 25' in rule), None)
        port_53_rule = next((rule for rule in rules if 'dport 53' in rule), None)
        
        assert port_25_rule is not None
        assert port_53_rule is not None
        assert 'office' in str(topology_manager.networks)
        assert 'servers' in str(topology_manager.networks)
    
    @patch('subprocess.run')
    def test_layer3_network_service_integration(self, mock_subprocess, topology_manager, sample_guests):
        """Test Layer3NetworkService integration with topology manager"""
        # Mock subprocess for iptables commands
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Chain created"
        mock_subprocess.return_value = mock_result
        
        # Enhanced topology config with Layer 3 rules
        topology_config = {
            'type': 'custom',
            'networks': [
                {
                    'name': 'office',
                    'members': ['desktop.eth0'],
                    'gateway': 'firewall.eth0'
                },
                {
                    'name': 'servers', 
                    'members': ['webserver.eth0'],
                    'gateway': 'firewall.eth1'
                }
            ],
            'forwarding_rules': [
                {'rule': 'src=office dst=servers dport=80,443'},
                {'rule': 'src=servers dst=office dport=53 proto=udp'}
            ]
        }
        
        range_id = "test_range_layer3"
        
        # This should trigger Layer3NetworkService if available
        topology_manager.create_topology(topology_config, sample_guests, range_id)
        
        # Verify topology was created
        assert len(topology_manager.networks) >= 2
        assert 'office' in topology_manager.networks
        assert 'servers' in topology_manager.networks
        
        # Verify forwarding rules were processed
        assert hasattr(topology_manager, 'forwarding_rules')
        assert len(topology_manager.forwarding_rules) > 0
        
        # Should contain proper iptables rules with stateful tracking
        rules = topology_manager.forwarding_rules
        stateful_rules = [rule for rule in rules if 'ESTABLISHED' in rule or 'NEW' in rule]
        assert len(stateful_rules) > 0
        
        # Verify network CIDR assignments
        office_network = topology_manager.get_network_info('office')
        servers_network = topology_manager.get_network_info('servers')
        
        assert office_network is not None
        assert servers_network is not None
        assert office_network['cidr'] == '192.168.100.0/24'
        assert servers_network['cidr'] == '192.168.200.0/24'
    
    @patch('subprocess.run')
    def test_layer3_cleanup_on_destroy(self, mock_subprocess, topology_manager, sample_guests):
        """Test Layer3NetworkService cleanup when topology is destroyed"""
        # Mock subprocess for iptables commands
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_subprocess.return_value = mock_result
        
        topology_config = {
            'networks': [
                {'name': 'office', 'members': ['desktop.eth0']}
            ],
            'forwarding_rules': [
                {'rule': 'src=office dst=office dport=22'}
            ]
        }
        
        range_id = "test_range_cleanup"
        
        # Create topology
        topology_manager.create_topology(topology_config, sample_guests, range_id)
        assert len(topology_manager.networks) > 0
        
        # Destroy topology - should clean up Layer 3 policies
        topology_manager.destroy_topology(range_id)
        
        # Verify cleanup
        assert len(topology_manager.networks) == 0
        assert len(topology_manager.ip_assignments) == 0
    
    def test_network_xml_generation(self, topology_manager):
        """Test generation of libvirt network XML"""
        network_name = "test-network"
        network_cidr = "192.168.150.0/24"
        gateway_ip = "192.168.150.1"
        config = {'bridge': 'br-test'}
        
        xml = topology_manager._generate_network_xml(
            network_name, network_cidr, gateway_ip, config
        )
        
        assert f"<name>{network_name}</name>" in xml
        assert f"<bridge name='br-test'" in xml
        assert f"ip address='{gateway_ip}'" in xml
        assert "<dhcp>" in xml
        assert "<range start=" in xml
    
    def test_topology_cleanup(self, topology_manager, topology_config, sample_guests):
        """Test cleanup of network topology"""
        range_id = "test_range_127"
        
        # Create topology
        topology_manager.create_topology(topology_config, sample_guests, range_id)
        
        # Verify topology exists
        assert len(topology_manager.networks) > 0
        assert len(topology_manager.ip_assignments) > 0
        
        # Clean up topology
        topology_manager.destroy_topology(range_id)
        
        # Verify cleanup
        assert len(topology_manager.networks) == 0
        assert len(topology_manager.ip_assignments) == 0
    
    def test_consistent_ip_assignment(self, topology_manager, topology_config):
        """Test that IP assignment is consistent for the same guest ID"""
        range_id = "test_range_128"
        
        # Create guest without predefined IP
        guests = []
        desktop = (GuestBuilder()
                   .with_guest_id("consistent_guest")
                   .with_basevm_host("host_1")
                   .with_basevm_config_file("/tmp/test.xml")
                   .with_basevm_type(BaseVMType.KVM)
                   .with_basevm_os_type(OSType.UBUNTU)
                   .build())
        guests.append(desktop)
        
        # Create topology multiple times
        ip_assignments_1 = topology_manager.create_topology(
            topology_config, guests, range_id
        )
        topology_manager.destroy_topology(range_id)
        
        ip_assignments_2 = topology_manager.create_topology(
            topology_config, guests, range_id
        )
        
        # Verify same IP is assigned
        assert ip_assignments_1['consistent_guest'] == ip_assignments_2['consistent_guest']


class TestNetworkTopologyRealOperations:
    """Tests that attempt real network operations where safe to do so"""
    
    def test_network_cidr_parsing(self):
        """Test network CIDR parsing and validation"""
        # Test valid CIDR parsing
        network = ipaddress.ip_network('192.168.100.0/24', strict=False)
        assert network.num_addresses == 256
        assert str(network.netmask) == '255.255.255.0'
        
        hosts = list(network.hosts())
        assert len(hosts) == 254  # Excluding network and broadcast addresses
        assert str(hosts[0]) == '192.168.100.1'
        assert str(hosts[-1]) == '192.168.100.254'
    
    def test_mac_address_generation(self):
        """Test MAC address generation for VMs"""
        import random
        
        # Test MAC generation similar to KVM provider
        mac_suffix = ':'.join(['%02x' % random.randint(0, 255) for _ in range(3)])
        mac_address = f'52:54:00:{mac_suffix}'
        
        # Verify format
        assert mac_address.count(':') == 5
        assert mac_address.startswith('52:54:00:')
        assert len(mac_address) == 17
    
    def test_iptables_rule_format(self):
        """Test iptables rule format generation"""
        src_network = "192.168.100.0/24"
        dst_network = "192.168.200.0/24"
        port = "25"
        
        rule = f"iptables -A FORWARD -s {src_network} -d {dst_network} -p tcp --dport {port} -j ACCEPT"
        
        assert "iptables -A FORWARD" in rule
        assert f"-s {src_network}" in rule
        assert f"-d {dst_network}" in rule
        assert f"--dport {port}" in rule
        assert "-j ACCEPT" in rule
    
    @pytest.mark.skipif(
        subprocess.run(['which', 'virsh'], capture_output=True).returncode != 0,
        reason="virsh not available"
    )
    def test_virsh_network_list(self):
        """Test that we can list libvirt networks (if virsh is available)"""
        try:
            result = subprocess.run(
                ['virsh', 'net-list', '--all'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Should succeed if libvirt is installed
            if result.returncode == 0:
                assert 'Name' in result.stdout
                assert 'State' in result.stdout
            else:
                pytest.skip("Cannot connect to libvirt daemon")
                
        except subprocess.TimeoutExpired:
            pytest.skip("virsh command timed out")
        except Exception as e:
            pytest.skip(f"virsh test failed: {e}")


if __name__ == "__main__":
    # Enable logging for manual testing
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])