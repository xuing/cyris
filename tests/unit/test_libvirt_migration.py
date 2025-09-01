"""
Comprehensive Test Suite for LibVirt-Python Migration

Tests for the new libvirt-python based components with TDD methodology.
Ensures functionality preservation and performance improvements.
"""

import pytest
import libvirt
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Import modules under test
from src.cyris.infrastructure.providers.libvirt_connection_manager import (
    LibvirtConnectionManager,
    ConnectionInfo,
    DomainInfo,
    LibvirtConnectionError,
    LibvirtDomainError,
    get_connection_manager,
    cleanup_all_managers
)

from src.cyris.infrastructure.providers.libvirt_domain_wrapper import (
    LibvirtDomainWrapper,
    DomainState,
    DomainStateInfo,
    NetworkInterface,
    DiskInfo
)


class TestLibvirtConnectionManager:
    """Test cases for LibvirtConnectionManager"""
    
    @pytest.fixture
    def mock_libvirt_open(self):
        """Mock libvirt.open to avoid actual connections"""
        with patch('libvirt.open') as mock_open:
            mock_conn = Mock()
            mock_conn.getHostname.return_value = "test-host"
            mock_conn.close.return_value = None
            mock_open.return_value = mock_conn
            yield mock_open, mock_conn
    
    @pytest.fixture  
    def connection_manager(self, mock_libvirt_open):
        """Create test connection manager"""
        mock_open, mock_conn = mock_libvirt_open
        manager = LibvirtConnectionManager("test:///default", timeout=10)
        return manager, mock_conn
    
    def test_connection_manager_initialization(self, mock_libvirt_open):
        """Test connection manager initialization and connection test"""
        mock_open, mock_conn = mock_libvirt_open
        
        manager = LibvirtConnectionManager("test:///default")
        
        # Should test connection on init
        mock_open.assert_called()
        mock_conn.getHostname.assert_called()
        assert manager.uri == "test:///default"
    
    def test_connection_manager_initialization_failure(self):
        """Test connection manager initialization failure handling"""
        with patch('libvirt.open', return_value=None):
            with pytest.raises(LibvirtConnectionError):
                LibvirtConnectionManager("invalid:///uri")
    
    def test_get_connection_creates_new(self, connection_manager):
        """Test that get_connection creates new connection"""
        manager, mock_conn = connection_manager
        
        with patch('libvirt.open', return_value=mock_conn) as mock_open:
            conn = manager.get_connection()
            
            assert conn == mock_conn
            assert manager.stats['connections_created'] == 2  # 1 for init + 1 for get_connection
    
    def test_get_connection_reuses_existing(self, connection_manager):
        """Test that get_connection reuses existing valid connections"""
        manager, mock_conn = connection_manager
        
        with patch('libvirt.open', return_value=mock_conn):
            # First call creates connection
            conn1 = manager.get_connection()
            
            # Second call should reuse
            conn2 = manager.get_connection() 
            
            assert conn1 == conn2
            assert manager.stats['connections_reused'] >= 1
    
    def test_connection_pooling_max_limit(self, mock_libvirt_open):
        """Test connection pool respects maximum connection limit"""
        mock_open, mock_conn = mock_libvirt_open
        
        manager = LibvirtConnectionManager("test:///default", max_connections=2)
        
        with patch('libvirt.open', return_value=mock_conn):
            # Create connections for different URIs
            conn1 = manager.get_connection("test:///uri1")
            conn2 = manager.get_connection("test:///uri2")
            conn3 = manager.get_connection("test:///uri3")  # Should trigger cleanup
            
            assert len(manager._connections) <= manager.max_connections
    
    def test_get_domain_success(self, connection_manager):
        """Test successful domain lookup"""
        manager, mock_conn = connection_manager
        mock_domain = Mock()
        mock_conn.lookupByName.return_value = mock_domain
        
        with patch('libvirt.open', return_value=mock_conn):
            domain = manager.get_domain("test-domain")
            
            assert domain == mock_domain
            mock_conn.lookupByName.assert_called_with("test-domain")
    
    def test_get_domain_not_found(self, connection_manager):
        """Test domain lookup when domain doesn't exist"""
        manager, mock_conn = connection_manager
        
        libvirt_error = libvirt.libvirtError("Domain not found")
        libvirt_error.get_error_code = lambda: libvirt.VIR_ERR_NO_DOMAIN
        mock_conn.lookupByName.side_effect = libvirt_error
        
        with patch('libvirt.open', return_value=mock_conn):
            with pytest.raises(LibvirtDomainError, match="Domain not found: test-domain"):
                manager.get_domain("test-domain")
    
    def test_list_domains_active_only(self, connection_manager):
        """Test listing only active domains"""
        manager, mock_conn = connection_manager
        mock_domains = [Mock(), Mock()]
        mock_conn.listDomainsID.return_value = [1, 2]
        mock_conn.lookupByID.side_effect = mock_domains
        
        with patch('libvirt.open', return_value=mock_conn):
            domains = manager.list_domains(active_only=True)
            
            assert domains == mock_domains
            mock_conn.listDomainsID.assert_called_once()
    
    def test_list_domains_all(self, connection_manager):
        """Test listing all domains"""
        manager, mock_conn = connection_manager
        mock_domains = [Mock(), Mock(), Mock()]
        mock_conn.listAllDomains.return_value = mock_domains
        
        with patch('libvirt.open', return_value=mock_conn):
            domains = manager.list_domains(active_only=False)
            
            assert domains == mock_domains
            mock_conn.listAllDomains.assert_called_once()
    
    def test_get_domain_info(self, connection_manager):
        """Test getting comprehensive domain information"""
        manager, mock_conn = connection_manager
        
        mock_domain = Mock()
        mock_domain.name.return_value = "test-vm"
        mock_domain.UUIDString.return_value = "test-uuid"
        mock_domain.state.return_value = (libvirt.VIR_DOMAIN_RUNNING, 0)
        mock_domain.info.return_value = [1, 2048000, 1024000, 2, 12345]
        mock_domain.isActive.return_value = True
        mock_domain.ID.return_value = 5
        
        mock_conn.lookupByName.return_value = mock_domain
        
        with patch('libvirt.open', return_value=mock_conn):
            info = manager.get_domain_info("test-vm")
            
            assert isinstance(info, DomainInfo)
            assert info.name == "test-vm"
            assert info.uuid == "test-uuid"
            assert info.state == (libvirt.VIR_DOMAIN_RUNNING, 0)
            assert info.is_active
    
    def test_connection_context_manager(self, connection_manager):
        """Test connection context manager"""
        manager, mock_conn = connection_manager
        
        with patch('libvirt.open', return_value=mock_conn):
            with manager.connection_context() as conn:
                assert conn == mock_conn
                # Connection should still be valid during context
                conn.getHostname()
    
    def test_reconnect_clears_cache(self, connection_manager):
        """Test that reconnect clears cached connections"""
        manager, mock_conn = connection_manager
        
        with patch('libvirt.open', return_value=mock_conn):
            # First connection
            conn1 = manager.get_connection()
            
            # Force reconnect
            conn2 = manager.reconnect()
            
            assert manager.stats['reconnections'] >= 1
    
    def test_close_all_connections(self, connection_manager):
        """Test closing all connections"""
        manager, mock_conn = connection_manager
        
        with patch('libvirt.open', return_value=mock_conn):
            # Create some connections
            manager.get_connection("test:///uri1")
            manager.get_connection("test:///uri2")
            
            # Close all
            manager.close_all_connections()
            
            assert len(manager._connections) == 0
    
    def test_health_check(self, connection_manager):
        """Test connection health check"""
        manager, mock_conn = connection_manager
        
        with patch('libvirt.open', return_value=mock_conn):
            manager.get_connection()
            
            health = manager.health_check()
            
            assert 'healthy_connections' in health
            assert 'unhealthy_connections' in health
            assert health['libvirt_available']
    
    def test_thread_safety(self, mock_libvirt_open):
        """Test thread safety of connection manager"""
        mock_open, mock_conn = mock_libvirt_open
        
        manager = LibvirtConnectionManager("test:///default")
        results = []
        errors = []
        
        def worker():
            try:
                with patch('libvirt.open', return_value=mock_conn):
                    conn = manager.get_connection()
                    results.append(conn)
                    time.sleep(0.01)  # Small delay to test concurrency
            except Exception as e:
                errors.append(e)
        
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 10


class TestLibvirtDomainWrapper:
    """Test cases for LibvirtDomainWrapper"""
    
    @pytest.fixture
    def mock_domain(self):
        """Mock libvirt domain object"""
        domain = Mock()
        domain.name.return_value = "test-vm"
        domain.UUIDString.return_value = "test-uuid"
        domain.isActive.return_value = True
        domain.state.return_value = (libvirt.VIR_DOMAIN_RUNNING, 0)
        domain.info.return_value = [1, 2048000, 1024000, 2, 12345]
        domain.isPersistent.return_value = 1
        domain.autostart.return_value = 0
        domain.ID.return_value = 5
        
        # Mock XML configuration
        mock_xml = '''
        <domain type='kvm'>
            <name>test-vm</name>
            <uuid>test-uuid</uuid>
            <devices>
                <interface type='bridge'>
                    <mac address='52:54:00:12:34:56'/>
                    <source bridge='virbr0'/>
                    <target dev='vnet0'/>
                </interface>
                <disk type='file' device='disk'>
                    <driver name='qemu' type='qcow2'/>
                    <source file='/var/lib/libvirt/images/test-vm.qcow2'/>
                    <target dev='vda' bus='virtio'/>
                </disk>
            </devices>
        </domain>
        '''
        domain.XMLDesc.return_value = mock_xml
        
        return domain
    
    @pytest.fixture
    def domain_wrapper(self, mock_domain):
        """Create domain wrapper with mocked domain"""
        return LibvirtDomainWrapper(mock_domain)
    
    def test_domain_wrapper_initialization(self, mock_domain):
        """Test domain wrapper initialization"""
        wrapper = LibvirtDomainWrapper(mock_domain)
        
        assert wrapper.name == "test-vm"
        assert wrapper.uuid == "test-uuid"
        assert wrapper.domain == mock_domain
    
    def test_from_name_class_method(self, mock_domain):
        """Test creating wrapper from domain name"""
        mock_manager = Mock()
        mock_manager.get_domain.return_value = mock_domain
        
        wrapper = LibvirtDomainWrapper.from_name("test-vm", mock_manager)
        
        assert wrapper.name == "test-vm"
        mock_manager.get_domain.assert_called_with("test-vm")
    
    def test_get_ip_addresses_via_interfaces(self, domain_wrapper, mock_domain):
        """Test IP address discovery via libvirt interfaces"""
        # Mock interfaceAddresses response
        interfaces_data = {
            'vnet0': {
                'addrs': [
                    {'type': libvirt.VIR_IP_ADDR_TYPE_IPV4, 'addr': '192.168.1.100', 'prefix': 24}
                ],
                'hwaddr': '52:54:00:12:34:56'
            }
        }
        mock_domain.interfaceAddresses.return_value = interfaces_data
        
        ips = domain_wrapper.get_ip_addresses()
        
        assert '192.168.1.100' in ips
        mock_domain.interfaceAddresses.assert_called_once()
    
    def test_get_ip_addresses_fallback_methods(self, domain_wrapper, mock_domain):
        """Test IP address discovery fallback methods"""
        # Make interfaceAddresses fail
        mock_domain.interfaceAddresses.side_effect = libvirt.libvirtError("Not supported")
        
        # Should fallback to XML parsing and other methods
        ips = domain_wrapper.get_ip_addresses()
        
        # Even if no IPs found, should not raise exception
        assert isinstance(ips, list)
    
    def test_get_mac_addresses(self, domain_wrapper):
        """Test MAC address extraction"""
        macs = domain_wrapper.get_mac_addresses()
        
        assert '52:54:00:12:34:56' in macs
    
    def test_get_network_interfaces(self, domain_wrapper):
        """Test network interface information extraction"""
        interfaces = domain_wrapper.get_network_interfaces()
        
        assert len(interfaces) == 1
        iface = interfaces[0]
        assert iface.mac_address == '52:54:00:12:34:56'
        assert iface.bridge == 'virbr0'
        assert iface.name == 'vnet0'
    
    def test_get_state_info(self, domain_wrapper):
        """Test comprehensive state information"""
        state_info = domain_wrapper.get_state_info()
        
        assert isinstance(state_info, DomainStateInfo)
        assert state_info.name == "test-vm"
        assert state_info.uuid == "test-uuid"
        assert state_info.state == DomainState.RUNNING
        assert state_info.is_active
        assert state_info.is_persistent
        assert not state_info.autostart
    
    def test_get_disk_info(self, domain_wrapper):
        """Test disk information extraction"""
        disks = domain_wrapper.get_disk_info()
        
        assert len(disks) == 1
        disk = disks[0]
        assert disk.target == 'vda'
        assert disk.source == '/var/lib/libvirt/images/test-vm.qcow2'
        assert disk.driver_type == 'qcow2'
        assert disk.bus == 'virtio'
    
    def test_xml_config_caching(self, domain_wrapper, mock_domain):
        """Test XML configuration caching"""
        # First call should fetch from domain
        xml1 = domain_wrapper.get_xml_config()
        mock_domain.XMLDesc.assert_called_once()
        
        # Second call should use cache
        xml2 = domain_wrapper.get_xml_config()
        # XMLDesc should still only be called once
        mock_domain.XMLDesc.assert_called_once()
        
        assert xml1 == xml2
    
    def test_domain_lifecycle_operations(self, domain_wrapper, mock_domain):
        """Test domain lifecycle operations (start, stop, etc.)"""
        # Test start
        mock_domain.isActive.return_value = False
        result = domain_wrapper.start()
        assert result
        mock_domain.create.assert_called_once()
        
        # Test destroy
        mock_domain.isActive.return_value = True
        result = domain_wrapper.destroy()
        assert result
        mock_domain.destroy.assert_called_once()
        
        # Test undefine
        mock_domain.isActive.return_value = False
        result = domain_wrapper.undefine()
        assert result
        mock_domain.undefine.assert_called_once()
    
    def test_error_handling(self, domain_wrapper, mock_domain):
        """Test error handling in various operations"""
        # Test libvirt error handling
        mock_domain.state.side_effect = libvirt.libvirtError("Connection lost")
        
        with pytest.raises(LibvirtDomainError):
            domain_wrapper.get_state_info()
    
    def test_string_representations(self, domain_wrapper):
        """Test string representations"""
        str_repr = str(domain_wrapper)
        assert "test-vm" in str_repr
        
        repr_str = repr(domain_wrapper)
        assert "test-vm" in repr_str
        assert "test-uuid" in repr_str


class TestIntegrationScenarios:
    """Integration test scenarios"""
    
    def test_manager_and_wrapper_integration(self):
        """Test integration between connection manager and domain wrapper"""
        # Mock everything for integration test
        with patch('libvirt.open') as mock_open:
            mock_conn = Mock()
            mock_conn.getHostname.return_value = "test-host"
            mock_open.return_value = mock_conn
            
            mock_domain = Mock()
            mock_domain.name.return_value = "integration-test-vm"
            mock_conn.lookupByName.return_value = mock_domain
            
            # Create manager and get domain through wrapper
            manager = LibvirtConnectionManager("test:///default")
            wrapper = LibvirtDomainWrapper.from_name("integration-test-vm", manager)
            
            assert wrapper.name == "integration-test-vm"
    
    def test_performance_benchmarking_setup(self):
        """Setup for performance benchmarking (placeholder)"""
        # This would contain actual performance tests comparing
        # libvirt-python vs virsh command performance
        pass


class TestGlobalManagerFunctions:
    """Test global manager functions"""
    
    def test_get_connection_manager_singleton(self):
        """Test singleton behavior of global connection manager"""
        with patch('src.cyris.infrastructure.providers.libvirt_connection_manager.LibvirtConnectionManager') as MockManager:
            mock_instance = Mock()
            MockManager.return_value = mock_instance
            
            # First call should create manager
            manager1 = get_connection_manager("test:///uri1")
            MockManager.assert_called_with("test:///uri1")
            
            # Second call with same URI should return same instance
            manager2 = get_connection_manager("test:///uri1")
            assert manager1 == manager2
            
            # Different URI should create new instance
            manager3 = get_connection_manager("test:///uri2")
            assert manager3 != manager1
    
    def test_cleanup_all_managers(self):
        """Test cleanup of all global managers"""
        with patch('src.cyris.infrastructure.providers.libvirt_connection_manager._connection_managers') as mock_managers:
            mock_manager = Mock()
            mock_managers.values.return_value = [mock_manager]
            mock_managers.clear.return_value = None
            
            cleanup_all_managers()
            
            mock_manager.close_all_connections.assert_called_once()
            mock_managers.clear.assert_called_once()


# Performance benchmarking utilities
class PerformanceBenchmark:
    """Utilities for benchmarking libvirt-python vs virsh performance"""
    
    @staticmethod
    def time_operation(func, *args, **kwargs):
        """Time an operation and return duration"""
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        return result, duration
    
    @staticmethod
    def compare_ip_discovery_methods():
        """Compare IP discovery performance between methods"""
        # This would implement actual performance comparison
        # between libvirt-python and virsh commands
        pass


if __name__ == "__main__":
    # Run tests with performance reporting
    pytest.main([
        __file__, 
        "-v", 
        "--tb=short",
        "--durations=10"  # Show 10 slowest tests
    ])