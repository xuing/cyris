"""
Test Network Configuration improvements
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# Add src path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from cyris.infrastructure.providers.kvm_provider import KVMProvider


class TestNetworkConfiguration(unittest.TestCase):
    """Test cases for network configuration improvements"""

    def setUp(self):
        """Set up test fixtures"""
        self.provider_config = {
            'libvirt_uri': 'qemu:///test',
            'network_mode': 'bridge',
            'enable_ssh': True
        }
        self.provider = KVMProvider(self.provider_config)

    @patch('cyris.infrastructure.providers.kvm_provider.subprocess')
    def test_bridge_networking_preservation_with_existing_bridge(self, mock_subprocess):
        """Test that bridge networking is preserved when bridge exists"""
        # Mock successful bridge check
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        
        # Create XML element with bridge type
        interface_xml = """
        <interface type='bridge'>
            <source bridge='virbr0'/>
            <mac address='52:54:00:12:34:56'/>
        </interface>
        """
        interface_elem = ET.fromstring(interface_xml)
        
        # Configure network interface
        self.provider._configure_network_interface(interface_elem)
        
        # Should preserve bridge configuration
        self.assertEqual(interface_elem.get('type'), 'bridge')
        source_elem = interface_elem.find('source')
        self.assertIsNotNone(source_elem)
        self.assertEqual(source_elem.get('bridge'), 'virbr0')

    @patch('cyris.infrastructure.providers.kvm_provider.subprocess')
    def test_bridge_fallback_when_bridge_missing(self, mock_subprocess):
        """Test fallback to network mode when bridge doesn't exist"""
        # Mock failed bridge check
        mock_result = Mock()
        mock_result.returncode = 1
        mock_subprocess.run.return_value = mock_result
        
        # Create XML element with bridge type
        interface_xml = """
        <interface type='bridge'>
            <source bridge='nonexistent'/>
            <mac address='52:54:00:12:34:56'/>
        </interface>
        """
        interface_elem = ET.fromstring(interface_xml)
        
        # Configure network interface
        self.provider._configure_network_interface(interface_elem)
        
        # Should fallback to network mode
        self.assertEqual(interface_elem.get('type'), 'network')
        source_elem = interface_elem.find('source')
        self.assertIsNotNone(source_elem)
        self.assertEqual(source_elem.get('network'), 'default')
        self.assertIsNone(source_elem.get('bridge'))

    def test_system_mode_network_configuration(self):
        """Test network configuration in system mode"""
        # Configure for system mode
        system_provider = KVMProvider({
            'libvirt_uri': 'qemu:///system',
            'network_mode': 'bridge',
            'enable_ssh': True
        })
        
        # Create XML element
        interface_xml = """
        <interface type='bridge'>
            <source bridge='virbr0'/>
            <mac address='52:54:00:12:34:56'/>
        </interface>
        """
        interface_elem = ET.fromstring(interface_xml)
        
        # Configure network interface
        system_provider._configure_network_interface(interface_elem)
        
        # Should use network mode for system
        self.assertEqual(interface_elem.get('type'), 'network')
        source_elem = interface_elem.find('source')
        self.assertEqual(source_elem.get('network'), 'default')

    def test_user_mode_configuration(self):
        """Test user mode configuration"""
        user_provider = KVMProvider({
            'libvirt_uri': 'qemu:///session',
            'network_mode': 'user',
            'enable_ssh': False
        })
        
        # Create XML element
        interface_xml = """
        <interface type='bridge'>
            <source bridge='virbr0'/>
            <mac address='52:54:00:12:34:56'/>
        </interface>
        """
        interface_elem = ET.fromstring(interface_xml)
        
        # Configure network interface
        user_provider._configure_network_interface(interface_elem)
        
        # Should use user mode
        self.assertEqual(interface_elem.get('type'), 'user')
        # Source element should be removed for user networking
        source_elem = interface_elem.find('source')
        self.assertIsNone(source_elem)

    @patch('subprocess.run')
    def test_bridge_check_exception_fallback(self, mock_subprocess_run):
        """Test fallback when bridge check throws exception"""
        # Configure provider for session mode to trigger bridge check
        session_provider = KVMProvider({
            'libvirt_uri': 'qemu:///session',
            'network_mode': 'bridge',
            'enable_ssh': True
        })
        
        # Mock subprocess exception
        mock_subprocess_run.side_effect = Exception("Network error")
        
        # Create XML element with bridge type
        interface_xml = """
        <interface type='bridge'>
            <source bridge='virbr0'/>
            <mac address='52:54:00:12:34:56'/>
        </interface>
        """
        interface_elem = ET.fromstring(interface_xml)
        
        # Configure network interface
        session_provider._configure_network_interface(interface_elem)
        
        # Should fallback to user mode on exception
        self.assertEqual(interface_elem.get('type'), 'user')
        source_elem = interface_elem.find('source')
        self.assertIsNone(source_elem)

    def test_network_mode_bridge_enables_ssh_by_default(self):
        """Test that bridge mode implies SSH should be enabled"""
        provider = KVMProvider({
            'libvirt_uri': 'qemu:///session',
            'network_mode': 'bridge',
            'enable_ssh': False  # Even if SSH is disabled, bridge mode should configure networking
        })
        
        # Create XML element
        interface_xml = """
        <interface type='user'>
            <mac address='52:54:00:12:34:56'/>
        </interface>
        """
        interface_elem = ET.fromstring(interface_xml)
        
        # Configure network interface
        provider._configure_network_interface(interface_elem)
        
        # Bridge mode should configure network mode even if SSH is disabled
        self.assertEqual(interface_elem.get('type'), 'network')


class TestSSHInfoCommand(unittest.TestCase):
    """Test SSH info command improvements"""

    def test_vm_resource_string_handling(self):
        """Test that SSH info correctly handles string VM resources"""
        from cyris.cli.commands.ssh_command import SSHInfoCommandHandler
        from cyris.config.settings import CyRISSettings
        
        config = CyRISSettings()
        handler = SSHInfoCommandHandler(config, verbose=False)
        
        # Mock provider with get_vm_ip method
        mock_provider = Mock()
        mock_provider.get_vm_ip.return_value = "192.168.1.100"
        mock_provider.get_vm_ssh_info.return_value = {
            'connection_type': 'bridge',
            'network': 'default',
            'mac_address': '52:54:00:12:34:56',
            'ssh_port': 22
        }
        
        # Test with list of string VM IDs (not dictionaries)
        vm_list = ["vm-1", "vm-2", "vm-3"]
        
        # This should not throw an exception
        try:
            with patch.object(handler, 'console') as mock_console:
                handler._display_vm_ssh_info(vm_list, mock_provider)
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success, "SSH info should handle string VM resources without exceptions")

    def test_vm_resource_dict_handling(self):
        """Test that SSH info still handles dict VM resources"""
        from cyris.cli.commands.ssh_command import SSHInfoCommandHandler
        from cyris.config.settings import CyRISSettings
        
        config = CyRISSettings()
        handler = SSHInfoCommandHandler(config, verbose=False)
        
        # Mock provider
        mock_provider = Mock()
        mock_provider.get_vm_ip.return_value = "192.168.1.100"
        mock_provider.get_vm_ssh_info.return_value = {
            'connection_type': 'bridge',
            'network': 'default'
        }
        
        # Test with list of dict VM resources
        vm_list = [
            {"id": "vm-1", "name": "test-vm-1"},
            {"id": "vm-2", "name": "test-vm-2"}
        ]
        
        # This should also not throw an exception
        try:
            with patch.object(handler, 'console') as mock_console:
                handler._display_vm_ssh_info(vm_list, mock_provider)
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success, "SSH info should handle dict VM resources without exceptions")


if __name__ == '__main__':
    unittest.main()