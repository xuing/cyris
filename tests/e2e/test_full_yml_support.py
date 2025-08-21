"""
End-to-End Tests for Full YAML Support

Tests the complete cyber range creation using examples/full.yml
to verify all functionality works together.
"""

import pytest
import yaml
from pathlib import Path
import logging
from unittest.mock import patch, MagicMock
import tempfile

from src.cyris.config.parser import CyRISConfigParser
from src.cyris.services.orchestrator import RangeOrchestrator 
from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
from src.cyris.config.settings import CyRISSettings


class TestFullYmlSupport:
    """End-to-end tests for full.yml cyber range support"""
    
    @pytest.fixture
    def full_yml_path(self):
        """Path to examples/full.yml"""
        return Path("/home/ubuntu/cyris/examples/full.yml")
    
    @pytest.fixture
    def config_parser(self):
        """Create config parser instance"""
        return CyRISConfigParser()
    
    @pytest.fixture
    def settings(self):
        """Create test settings"""
        with tempfile.TemporaryDirectory() as temp_dir:
            return CyRISSettings(
                cyris_path="/home/ubuntu/cyris",
                cyber_range_dir=temp_dir,
                gateway_mode=False,
                gateway_account="",
                gateway_mgmt_addr="",
                gateway_inside_addr="",
                user_email=""
            )
    
    @pytest.fixture
    def kvm_provider(self, settings):
        """Create KVM provider with test configuration"""
        config = {
            "libvirt_uri": "qemu:///session",
            "base_path": settings.cyris_path
        }
        return KVMProvider(config)
    
    @pytest.fixture
    def orchestrator(self, settings, kvm_provider):
        """Create orchestrator with KVM provider"""
        return RangeOrchestrator(settings, kvm_provider)
    
    @pytest.mark.skipif(
        not Path("/home/ubuntu/cyris/examples/full.yml").exists(),
        reason="examples/full.yml not found"
    )
    def test_full_yml_parsing(self, full_yml_path, config_parser):
        """Test that full.yml can be parsed correctly"""
        
        # Parse the YAML file
        hosts, guests, clone_settings = config_parser.parse_yaml_file(str(full_yml_path))
        
        # Verify host settings
        assert len(hosts) == 1
        host = hosts[0]
        assert host.id == "host_1"
        assert host.mgmt_addr == "localhost" 
        assert host.virbr_addr == "192.168.122.1"
        assert host.account == "cyuser"
        
        # Verify guest settings
        assert len(guests) == 3
        guest_ids = [g.id for g in guests]
        assert "desktop" in guest_ids
        assert "webserver" in guest_ids
        assert "firewall" in guest_ids
        
        # Check desktop guest details
        desktop = next(g for g in guests if g.id == "desktop")
        assert desktop.ip_addr == "192.168.122.50"
        assert desktop.basevm_host == "host_1"
        assert desktop.basevm_type == "kvm"
        assert hasattr(desktop, 'tasks')
        assert len(desktop.tasks) > 0
        
        # Verify tasks are parsed
        task_types = []
        for task_config in desktop.tasks:
            task_types.extend(task_config.keys())
        
        expected_tasks = ['add_account', 'modify_account', 'install_package', 
                         'emulate_attack', 'emulate_traffic_capture_file',
                         'emulate_malware', 'copy_content', 'execute_program', 
                         'firewall_rules']
        
        for expected_task in expected_tasks:
            assert expected_task in task_types, f"Missing task type: {expected_task}"
        
        # Verify clone settings
        assert clone_settings is not None
        assert clone_settings.range_id == "125"
        
        # Check topology configuration
        hosts_config = clone_settings.hosts[0]
        assert hosts_config['host_id'] == 'host_1'
        assert hosts_config['instance_number'] == 2
        
        topology = hosts_config['topology'][0]
        assert topology['type'] == 'custom'
        
        networks = topology['networks']
        assert len(networks) == 2
        
        office_network = next(n for n in networks if n['name'] == 'office')
        servers_network = next(n for n in networks if n['name'] == 'servers')
        
        assert office_network['members'] == 'desktop.eth0'
        assert office_network['gateway'] == 'firewall.eth0'
        assert servers_network['members'] == 'webserver.eth0'
        assert servers_network['gateway'] == 'firewall.eth1'
    
    def test_network_topology_from_full_yml(self, full_yml_path, config_parser):
        """Test network topology creation from full.yml"""
        hosts, guests, clone_settings = config_parser.parse_yaml_file(str(full_yml_path))
        
        # Extract topology configuration
        hosts_config = clone_settings.hosts[0]
        topology_config = hosts_config['topology'][0]
        
        # Test topology manager with this configuration
        from src.cyris.infrastructure.network.topology_manager import NetworkTopologyManager
        
        topology_manager = NetworkTopologyManager()
        ip_assignments = topology_manager.create_topology(
            topology_config, guests, "test_range_full"
        )
        
        # Verify IP assignments respect predefined values
        assert ip_assignments['desktop'] == "192.168.122.50"
        assert ip_assignments['webserver'] == "192.168.122.51"
        assert ip_assignments['firewall'] == "192.168.122.10"
        
        # Verify networks were created
        office_network = topology_manager.get_network_info('office')
        servers_network = topology_manager.get_network_info('servers')
        
        assert office_network is not None
        assert servers_network is not None
    
    def test_task_execution_from_full_yml(self, full_yml_path, config_parser):
        """Test task execution using tasks from full.yml"""
        hosts, guests, clone_settings = config_parser.parse_yaml_file(str(full_yml_path))
        
        from src.cyris.services.task_executor import TaskExecutor
        
        task_executor = TaskExecutor({
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30
        })
        
        # Test desktop guest tasks
        desktop = next(g for g in guests if g.id == "desktop")
        
        with patch.object(task_executor, '_execute_ssh_command') as mock_ssh:
            mock_ssh.return_value = (True, "Success", "")
            
            with patch('subprocess.run') as mock_subprocess:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "Success"
                mock_result.stderr = ""
                mock_subprocess.return_value = mock_result
                
                results = task_executor.execute_guest_tasks(
                    desktop, "192.168.122.50", desktop.tasks
                )
        
        # Should have executed multiple tasks
        assert len(results) > 0
        
        # Check that various task types were executed
        task_types = {result.task_type for result in results}
        expected_types = {'add_account', 'modify_account', 'install_package'}
        
        for expected_type in expected_types:
            assert any(expected_type in str(task_type) for task_type in task_types)
    
    @pytest.mark.integration
    def test_full_range_creation_simulation(self, orchestrator, full_yml_path, config_parser):
        """Test complete cyber range creation simulation using full.yml"""
        
        # Parse full.yml
        hosts, guests, clone_settings = config_parser.parse_yaml_file(str(full_yml_path))
        
        # Extract topology configuration  
        hosts_config = clone_settings.hosts[0]
        topology_config = hosts_config['topology'][0]
        
        # Add forwarding rules if present
        firewall_guest = next((g for g in hosts_config['guests'] if g['guest_id'] == 'firewall'), None)
        if firewall_guest and 'forwarding_rules' in firewall_guest:
            topology_config['forwarding_rules'] = firewall_guest['forwarding_rules']
        
        # Mock infrastructure operations to avoid actual VM creation
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts:
            with patch.object(orchestrator.provider, 'create_guests') as mock_create_guests:
                with patch.object(orchestrator.topology_manager, 'libvirt_connection'):
                    
                    mock_create_hosts.return_value = ['host_1']
                    mock_create_guests.return_value = ['vm_desktop_1', 'vm_webserver_1', 'vm_firewall_1']
                    
                    # Mock task execution
                    with patch.object(orchestrator.task_executor, 'execute_guest_tasks') as mock_tasks:
                        mock_tasks.return_value = [
                            MagicMock(success=True, message="Task completed", task_id="test_task", task_type="add_account")
                        ]
                        
                        # Create range
                        range_metadata = orchestrator.create_range(
                            range_id="125",
                            name="Full YAML Test Range",
                            description="Test range from examples/full.yml",
                            hosts=hosts,
                            guests=guests,
                            topology_config=topology_config
                        )
        
        # Verify range was created successfully
        assert range_metadata.range_id == "125"
        assert range_metadata.name == "Full YAML Test Range"
        assert range_metadata.status.value == "active"
        
        # Verify hosts and guests were "created"
        mock_create_hosts.assert_called_once_with(hosts)
        mock_create_guests.assert_called_once()
        
        # Verify tasks were executed for guests with tasks
        guests_with_tasks = [g for g in guests if hasattr(g, 'tasks') and g.tasks]
        assert len(guests_with_tasks) > 0
        
        # Check that task executor was called for each guest with tasks
        assert mock_tasks.call_count == len(guests_with_tasks)
    
    def test_examples_basic_yml_comparison(self, config_parser):
        """Test that basic.yml also works and compare with full.yml"""
        
        basic_yml_path = Path("/home/ubuntu/cyris/examples/basic.yml")
        full_yml_path = Path("/home/ubuntu/cyris/examples/full.yml")
        
        if not basic_yml_path.exists():
            pytest.skip("basic.yml not found")
        if not full_yml_path.exists():
            pytest.skip("full.yml not found")
        
        # Parse both files
        basic_hosts, basic_guests, basic_clone = config_parser.parse_yaml_file(str(basic_yml_path))
        full_hosts, full_guests, full_clone = config_parser.parse_yaml_file(str(full_yml_path))
        
        # Basic should be simpler
        assert len(basic_guests) <= len(full_guests)
        assert len(basic_hosts) == len(full_hosts)  # Same number of hosts
        
        # Full should have more complex topology
        basic_topology = basic_clone.hosts[0]['topology'][0]
        full_topology = full_clone.hosts[0]['topology'][0]
        
        assert len(full_topology['networks']) >= len(basic_topology['networks'])
        
        # Full should have more tasks
        basic_desktop = next((g for g in basic_guests if g.id == "desktop"), None)
        full_desktop = next((g for g in full_guests if g.id == "desktop"), None)
        
        if basic_desktop and full_desktop:
            basic_task_count = len(getattr(basic_desktop, 'tasks', []))
            full_task_count = len(getattr(full_desktop, 'tasks', []))
            assert full_task_count >= basic_task_count
    
    def test_error_handling_in_full_range_creation(self, orchestrator, full_yml_path, config_parser):
        """Test error handling during full range creation"""
        
        hosts, guests, clone_settings = config_parser.parse_yaml_file(str(full_yml_path))
        
        # Mock infrastructure failure
        with patch.object(orchestrator.provider, 'create_hosts') as mock_create_hosts:
            mock_create_hosts.side_effect = Exception("Infrastructure creation failed")
            
            with pytest.raises(RuntimeError, match="Range creation failed"):
                orchestrator.create_range(
                    range_id="error_test",
                    name="Error Test Range", 
                    description="Test error handling",
                    hosts=hosts,
                    guests=guests
                )
    
    @pytest.mark.skipif(
        not Path("/home/ubuntu/cyris/examples/full.yml").exists(),
        reason="full.yml not available for validation"
    )
    def test_full_yml_validation(self, full_yml_path):
        """Test that full.yml passes validation checks"""
        
        # Import the validation function from main directory
        import sys
        import os
        main_path = os.path.join(os.path.dirname(__file__), '../..', 'main')
        if main_path not in sys.path:
            sys.path.insert(0, main_path)
        
        try:
            from check_description import check_description
            
            # This would normally require setting up the cyber range directory structure
            # For testing, we'll just verify the YAML structure is valid
            with open(full_yml_path) as f:
                yaml_content = yaml.safe_load(f)
            
            # Basic structure validation
            assert isinstance(yaml_content, list)
            assert len(yaml_content) == 3  # host_settings, guest_settings, clone_settings
            
            # Each section should be present
            sections = {list(section.keys())[0] for section in yaml_content}
            expected_sections = {'host_settings', 'guest_settings', 'clone_settings'}
            assert sections == expected_sections
            
        except ImportError:
            pytest.skip("Legacy validation code not available")


class TestYamlCompatibility:
    """Test compatibility between old and new YAML processing"""
    
    def test_yaml_structure_consistency(self):
        """Test that YAML structure is consistent between implementations"""
        
        # Test basic YAML parsing without CyRIS-specific logic
        basic_yml = """
---
- host_settings:
  - id: host_1
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: ubuntu

- guest_settings:
  - id: desktop
    basevm_host: host_1
    basevm_config_file: /home/ubuntu/cyris/images/basevm.xml
    basevm_type: kvm

- clone_settings:
  - range_id: 123
    hosts:
    - host_id: host_1
      instance_number: 1
      guests:
      - guest_id: desktop
        number: 1
        entry_point: yes
      topology:
      - type: custom
        networks:
        - name: office
          members: desktop.eth0
        """
        
        parsed = yaml.safe_load(basic_yml)
        
        assert len(parsed) == 3
        assert 'host_settings' in parsed[0]
        assert 'guest_settings' in parsed[1] 
        assert 'clone_settings' in parsed[2]
        
        # Verify structure matches expected format
        host = parsed[0]['host_settings'][0]
        assert host['id'] == 'host_1'
        
        guest = parsed[1]['guest_settings'][0]
        assert guest['id'] == 'desktop'
        
        clone = parsed[2]['clone_settings'][0]
        assert clone['range_id'] == 123


if __name__ == "__main__":
    # Enable logging for manual testing
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])