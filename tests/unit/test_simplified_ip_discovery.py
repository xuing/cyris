"""
Unit tests for simplified IP discovery functionality.
Tests the new get_vm_ip_simple function and its helper methods.
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock, call
from typing import Optional, Tuple

from src.cyris.tools.vm_ip_manager import (
    get_vm_ip_simple,
    _get_ip_from_dhcp_leases,
    _get_ip_from_virsh,
    _get_ip_discovery_diagnostics
)


class TestSimplifiedIPDiscovery:
    """Test simplified IP discovery functionality"""
    
    def test_get_vm_ip_simple_success_dhcp(self):
        """Test successful IP discovery via DHCP leases"""
        vm_name = "test-vm"
        expected_ip = "192.168.122.100"
        
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases') as mock_dhcp:
            mock_dhcp.return_value = expected_ip
            
            ip, error = get_vm_ip_simple(vm_name)
            
            assert ip == expected_ip
            assert error is None
            mock_dhcp.assert_called_once_with(vm_name)
    
    def test_get_vm_ip_simple_success_virsh_fallback(self):
        """Test successful IP discovery via virsh fallback"""
        vm_name = "test-vm"
        expected_ip = "192.168.122.101"
        
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases') as mock_dhcp, \
             patch('src.cyris.tools.vm_ip_manager._get_ip_from_virsh') as mock_virsh:
            
            mock_dhcp.return_value = None  # DHCP fails
            mock_virsh.return_value = expected_ip  # virsh succeeds
            
            ip, error = get_vm_ip_simple(vm_name)
            
            assert ip == expected_ip
            assert error is None
            mock_dhcp.assert_called_once_with(vm_name)
            mock_virsh.assert_called_once_with(vm_name)
    
    def test_get_vm_ip_simple_no_ip_found(self):
        """Test when no IP is found, returns diagnostic info"""
        vm_name = "test-vm"
        expected_diagnostics = "VM Status: running; Network Interface: present"
        
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases') as mock_dhcp, \
             patch('src.cyris.tools.vm_ip_manager._get_ip_from_virsh') as mock_virsh, \
             patch('src.cyris.tools.vm_ip_manager._get_ip_discovery_diagnostics') as mock_diag:
            
            mock_dhcp.return_value = None
            mock_virsh.return_value = None
            mock_diag.return_value = expected_diagnostics
            
            ip, error = get_vm_ip_simple(vm_name)
            
            assert ip is None
            assert error == expected_diagnostics
            mock_diag.assert_called_once_with(vm_name)
    
    def test_get_vm_ip_simple_exception_handling(self):
        """Test exception handling in get_vm_ip_simple"""
        vm_name = "test-vm"
        exception_msg = "Connection failed"
        
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases') as mock_dhcp:
            mock_dhcp.side_effect = Exception(exception_msg)
            
            ip, error = get_vm_ip_simple(vm_name)
            
            assert ip is None
            assert f"IP Discovery Error: {exception_msg}" in error


class TestDHCPLeaseDiscovery:
    """Test DHCP lease discovery functionality"""
    
    def test_get_ip_from_dhcp_leases_success(self):
        """Test successful DHCP lease parsing"""
        vm_name = "cyris-desktop-abc123"
        dhcp_output = """
 Expiry Time           MAC address         Protocol   IP address           Hostname     Client ID or DUID
--------------------------------------------------------------------------------------------------------------------------------------------------
 2025-09-01 16:40:33   52:54:00:2b:06:c8   ipv4       192.168.122.230/24   -            client-id
 2025-09-01 16:26:31   52:54:00:2b:26:06   ipv4       192.168.122.63/24    cyris-desktop-abc123  client-id-2
"""
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = dhcp_output
        
        with patch('subprocess.run', return_value=mock_result):
            ip = _get_ip_from_dhcp_leases(vm_name)
            
            assert ip == "192.168.122.63"
    
    def test_get_ip_from_dhcp_leases_not_found(self):
        """Test when VM not in DHCP leases"""
        vm_name = "nonexistent-vm"
        dhcp_output = """
 Expiry Time           MAC address         Protocol   IP address           Hostname     Client ID or DUID
--------------------------------------------------------------------------------------------------------------------------------------------------
 2025-09-01 16:40:33   52:54:00:2b:06:c8   ipv4       192.168.122.230/24   other-vm     client-id
"""
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = dhcp_output
        
        with patch('subprocess.run', return_value=mock_result):
            ip = _get_ip_from_dhcp_leases(vm_name)
            
            assert ip is None
    
    def test_get_ip_from_dhcp_leases_command_failure(self):
        """Test when virsh command fails"""
        vm_name = "test-vm"
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "error: failed to get network interface info"
        
        with patch('subprocess.run', return_value=mock_result):
            ip = _get_ip_from_dhcp_leases(vm_name)
            
            assert ip is None
    
    def test_get_ip_from_dhcp_leases_timeout(self):
        """Test timeout handling"""
        vm_name = "test-vm"
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['virsh'], 10)):
            ip = _get_ip_from_dhcp_leases(vm_name)
            
            assert ip is None


class TestVirshDomifaddrDiscovery:
    """Test virsh domifaddr discovery functionality"""
    
    def test_get_ip_from_virsh_success(self):
        """Test successful virsh domifaddr parsing"""
        vm_name = "test-vm"
        virsh_output = """
 Name       MAC address          Protocol     Address
-------------------------------------------------------------------------------
 vnet0      52:54:00:2b:06:c8    ipv4         192.168.122.100/24
"""
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = virsh_output
        
        with patch('subprocess.run', return_value=mock_result):
            ip = _get_ip_from_virsh(vm_name)
            
            assert ip == "192.168.122.100"
    
    def test_get_ip_from_virsh_no_ip(self):
        """Test when domifaddr returns no IP"""
        vm_name = "test-vm"
        virsh_output = """
 Name       MAC address          Protocol     Address
-------------------------------------------------------------------------------
"""
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = virsh_output
        
        with patch('subprocess.run', return_value=mock_result):
            ip = _get_ip_from_virsh(vm_name)
            
            assert ip is None
    
    def test_get_ip_from_virsh_command_failure(self):
        """Test when virsh domifaddr command fails"""
        vm_name = "nonexistent-vm"
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        
        with patch('subprocess.run', return_value=mock_result):
            ip = _get_ip_from_virsh(vm_name)
            
            assert ip is None


class TestIPDiscoveryDiagnostics:
    """Test IP discovery diagnostics functionality"""
    
    def test_get_ip_discovery_diagnostics_complete(self):
        """Test complete diagnostic information gathering"""
        vm_name = "test-vm"
        
        # Mock VM state check
        mock_domstate = MagicMock()
        mock_domstate.returncode = 0
        mock_domstate.stdout = "running"
        
        # Mock XML check
        mock_dumpxml = MagicMock()
        mock_dumpxml.returncode = 0
        mock_dumpxml.stdout = "<domain><interface type='network'></interface></domain>"
        
        # Mock DHCP leases check
        mock_dhcp = MagicMock()
        mock_dhcp.returncode = 0
        mock_dhcp.stdout = """
 Expiry Time           MAC address         Protocol   IP address           Hostname     Client ID or DUID
--------------------------------------------------------------------------------------------------------------------------------------------------
 2025-09-01 16:40:33   52:54:00:2b:06:c8   ipv4       192.168.122.230/24   vm1          client-id-1
 2025-09-01 16:26:31   52:54:00:2b:26:06   ipv4       192.168.122.63/24    vm2          client-id-2
"""
        
        def mock_run(cmd, **kwargs):
            if 'domstate' in cmd:
                return mock_domstate
            elif 'dumpxml' in cmd:
                return mock_dumpxml
            elif 'net-dhcp-leases' in cmd:
                return mock_dhcp
            return MagicMock(returncode=1)
        
        with patch('subprocess.run', side_effect=mock_run):
            diagnostics = _get_ip_discovery_diagnostics(vm_name)
            
            expected = "VM Status: running; Network Interface: present; Active DHCP Leases: 2"
            assert diagnostics == expected
    
    def test_get_ip_discovery_diagnostics_vm_not_running(self):
        """Test diagnostics when VM is not running"""
        vm_name = "stopped-vm"
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "shut off"
        
        with patch('subprocess.run', return_value=mock_result):
            diagnostics = _get_ip_discovery_diagnostics(vm_name)
            
            assert "VM Status: shut off" in diagnostics
    
    def test_get_ip_discovery_diagnostics_no_network_interface(self):
        """Test diagnostics when VM has no network interface"""
        vm_name = "test-vm"
        
        # Mock successful domstate but no interface in XML
        def mock_run(cmd, **kwargs):
            mock_result = MagicMock()
            mock_result.returncode = 0
            
            if 'domstate' in cmd:
                mock_result.stdout = "running"
            elif 'dumpxml' in cmd:
                mock_result.stdout = "<domain><devices></devices></domain>"  # No interface
            elif 'net-dhcp-leases' in cmd:
                mock_result.stdout = "No leases found"
            
            return mock_result
        
        with patch('subprocess.run', side_effect=mock_run):
            diagnostics = _get_ip_discovery_diagnostics(vm_name)
            
            assert "Network Interface: missing or misconfigured" in diagnostics
    
    def test_get_ip_discovery_diagnostics_exception_handling(self):
        """Test exception handling in diagnostics"""
        vm_name = "test-vm"
        
        with patch('subprocess.run', side_effect=Exception("Command failed")):
            diagnostics = _get_ip_discovery_diagnostics(vm_name)
            
            assert "Diagnostic Error: Command failed" in diagnostics


class TestIntegrationScenarios:
    """Integration test scenarios combining multiple components"""
    
    def test_vm_lifecycle_ip_discovery(self):
        """Test IP discovery through VM lifecycle states"""
        vm_name = "lifecycle-test-vm"
        
        # Scenario 1: VM just created, no IP yet
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases', return_value=None), \
             patch('src.cyris.tools.vm_ip_manager._get_ip_from_virsh', return_value=None), \
             patch('src.cyris.tools.vm_ip_manager._get_ip_discovery_diagnostics', 
                   return_value="VM Status: running; Network Interface: present; Active DHCP Leases: 0"):
            
            ip, error = get_vm_ip_simple(vm_name)
            assert ip is None
            assert "Active DHCP Leases: 0" in error
        
        # Scenario 2: VM boots and gets IP
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases', 
                   return_value="192.168.122.150"):
            
            ip, error = get_vm_ip_simple(vm_name)
            assert ip == "192.168.122.150"
            assert error is None
    
    def test_error_propagation_chain(self):
        """Test error propagation through the discovery chain"""
        vm_name = "error-test-vm"
        
        # All methods fail, should return diagnostic info
        with patch('src.cyris.tools.vm_ip_manager._get_ip_from_dhcp_leases', return_value=None), \
             patch('src.cyris.tools.vm_ip_manager._get_ip_from_virsh', return_value=None), \
             patch('src.cyris.tools.vm_ip_manager._get_ip_discovery_diagnostics', 
                   return_value="VM Status: shut off; Network Interface: missing"):
            
            ip, error = get_vm_ip_simple(vm_name)
            assert ip is None
            assert "VM Status: shut off" in error
            assert "Network Interface: missing" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])