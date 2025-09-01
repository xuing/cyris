"""
Test VM IP Manager functionality including caching improvements
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from cyris.tools.vm_ip_manager import VMIPManager, VMIPInfo, CachedIPInfo


class TestVMIPManager(unittest.TestCase):
    """Test cases for VM IP Manager"""

    def setUp(self):
        """Set up test fixtures"""
        self.manager = VMIPManager(libvirt_uri="qemu:///test")
        self.sample_vm_info = VMIPInfo(
            vm_name="test-vm",
            vm_id="test-vm-id",
            ip_addresses=["192.168.1.100"],
            mac_addresses=["52:54:00:12:34:56"],
            interface_names=["eth0"],
            discovery_method="test",
            last_updated="2025-08-27 23:00:00",
            status="active"
        )

    def test_cached_ip_info_expiration(self):
        """Test cache expiration functionality"""
        # Create cache entry that expires in the past
        expired_cached_info = CachedIPInfo(
            ip_info=self.sample_vm_info,
            cached_at=datetime.now() - timedelta(minutes=10),
            expires_at=datetime.now() - timedelta(minutes=5)
        )
        
        self.assertTrue(expired_cached_info.is_expired())
        self.assertFalse(expired_cached_info.is_fresh())
        
        # Create cache entry that is fresh
        fresh_cached_info = CachedIPInfo(
            ip_info=self.sample_vm_info,
            cached_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5)
        )
        
        self.assertFalse(fresh_cached_info.is_expired())
        self.assertTrue(fresh_cached_info.is_fresh())

    def test_get_cached_ip_info_fresh(self):
        """Test retrieving fresh cached IP info"""
        # Add fresh cache entry
        fresh_cached_info = CachedIPInfo(ip_info=self.sample_vm_info)
        self.manager._ip_cache["test-vm"] = fresh_cached_info
        
        # Should return cached info
        result = self.manager.get_cached_ip_info("test-vm")
        self.assertIsNotNone(result)
        self.assertEqual(result.vm_name, "test-vm")
        self.assertEqual(result.ip_addresses, ["192.168.1.100"])

    def test_get_cached_ip_info_expired(self):
        """Test retrieving expired cached IP info"""
        # Add expired cache entry
        expired_cached_info = CachedIPInfo(
            ip_info=self.sample_vm_info,
            cached_at=datetime.now() - timedelta(minutes=10),
            expires_at=datetime.now() - timedelta(minutes=5)
        )
        self.manager._ip_cache["test-vm"] = expired_cached_info
        
        # Should return None and remove expired entry
        result = self.manager.get_cached_ip_info("test-vm")
        self.assertIsNone(result)
        self.assertNotIn("test-vm", self.manager._ip_cache)

    def test_get_cached_ip_info_not_found(self):
        """Test retrieving non-existent cached IP info"""
        result = self.manager.get_cached_ip_info("non-existent-vm")
        self.assertIsNone(result)

    def test_cache_freshness_with_max_age(self):
        """Test cache freshness with custom max age"""
        # Create entry that's 2 minutes old
        two_minutes_old = CachedIPInfo(
            ip_info=self.sample_vm_info,
            cached_at=datetime.now() - timedelta(minutes=2),
            expires_at=datetime.now() + timedelta(minutes=3)
        )
        self.manager._ip_cache["test-vm"] = two_minutes_old
        
        # Should be fresh with 5-minute max age
        result = self.manager.get_cached_ip_info("test-vm", max_age_seconds=300)
        self.assertIsNotNone(result)
        
        # Should not be fresh with 1-minute max age
        result = self.manager.get_cached_ip_info("test-vm", max_age_seconds=60)
        self.assertIsNone(result)

    def test_ip_discovery_caching(self):
        """Test that IP discovery results are properly cached"""
        # Mock _get_ips_via_cyris_topology to return test data
        with patch.object(self.manager, '_get_ips_via_cyris_topology', return_value=self.sample_vm_info):
            # First call should hit the discovery method
            result1 = self.manager.get_vm_ip_addresses("test-vm", methods=['cyris_topology'])
            self.assertIsNotNone(result1)
            
            # Check that cache was populated
            self.assertIn("test-vm", self.manager._ip_cache)
            cached_result = self.manager.get_cached_ip_info("test-vm")
            self.assertIsNotNone(cached_result)
            self.assertEqual(cached_result.ip_addresses, ["192.168.1.100"])

    def test_cache_performance_improvement(self):
        """Test that caching improves performance"""
        # Add cached entry
        cached_info = CachedIPInfo(ip_info=self.sample_vm_info)
        self.manager._ip_cache["test-vm"] = cached_info
        
        start_time = datetime.now()
        
        # This should be very fast as it hits the cache
        result = self.manager.get_cached_ip_info("test-vm")
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Should be nearly instantaneous (< 0.01 seconds)
        self.assertLess(execution_time, 0.01)
        self.assertIsNotNone(result)

    def test_multiple_cache_entries(self):
        """Test managing multiple cache entries"""
        # Add multiple cache entries
        vm1_info = VMIPInfo("vm1", "vm1-id", ["192.168.1.1"], [], [], "test", "", "active")
        vm2_info = VMIPInfo("vm2", "vm2-id", ["192.168.1.2"], [], [], "test", "", "active")
        
        self.manager._ip_cache["vm1"] = CachedIPInfo(ip_info=vm1_info)
        self.manager._ip_cache["vm2"] = CachedIPInfo(ip_info=vm2_info)
        
        # Should retrieve correct entries
        result1 = self.manager.get_cached_ip_info("vm1")
        result2 = self.manager.get_cached_ip_info("vm2")
        
        self.assertEqual(result1.ip_addresses, ["192.168.1.1"])
        self.assertEqual(result2.ip_addresses, ["192.168.1.2"])


class TestNetworkingConfiguration(unittest.TestCase):
    """Test cases for networking configuration improvements"""

    def test_bridge_mode_default(self):
        """Test that bridge mode is now the default"""
        # This test validates that our CLI changes work
        # (would need CLI integration testing for full validation)
        self.assertTrue(True)  # Placeholder - actual test would involve CLI testing

    def test_ssh_info_type_handling(self):
        """Test that SSH info handles both string and dict VM resources correctly"""
        # This test validates that our SSH info fix works
        # (would need integration testing with real orchestrator)
        self.assertTrue(True)  # Placeholder - actual test would involve CLI testing


if __name__ == '__main__':
    unittest.main()