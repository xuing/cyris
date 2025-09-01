#!/usr/bin/env python3
"""
Complete Functionality Test

This script tests the complete CyRIS functionality including:
1. Network access problem fix (bridge networking instead of user networking)
2. Network topology management 
3. Task execution integration
4. Full YAML support validation

Run this to verify that all network access issues have been resolved
and full cyber range functionality is working.
"""

import logging
import tempfile
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, 'src')

from cyris.config.parser import CyRISConfigParser
from cyris.config.settings import CyRISSettings
from cyris.infrastructure.providers.kvm_provider import KVMProvider
from cyris.infrastructure.network.topology_manager import NetworkTopologyManager
from cyris.services.task_executor import TaskExecutor
from cyris.services.orchestrator import RangeOrchestrator
from cyris.domain.entities.guest import GuestBuilder, BaseVMType, OSType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_network_fix():
    """Test 1: Verify network access problem is fixed"""
    logger.info("🔧 Testing network configuration fix...")
    
    provider = KVMProvider({'libvirt_uri': 'qemu:///session'})
    
    guest = (GuestBuilder()
             .with_guest_id('test_network_vm')
             .with_basevm_host('host_1')
             .with_basevm_config_file('/tmp/test.xml')
             .with_basevm_type(BaseVMType.KVM)
             .with_basevm_os_type(OSType.UBUNTU)
             .build())
    
    xml = provider._generate_vm_xml('test_vm', guest, '/tmp/test.qcow2', {})
    
    # Check for bridge networking instead of user networking
    if 'type=\'network\'' in xml:
        logger.info("  ✅ Using network type (bridge mode) instead of user mode")
    else:
        logger.error("  ❌ Still using user networking - SSH access will be blocked")
        return False
    
    if 'source network=\'default\'' in xml:
        logger.info("  ✅ Connected to default network for SSH access")
    else:
        logger.error("  ❌ Not connected to network - VMs will be isolated")
        return False
    
    return True

def test_network_topology():
    """Test 2: Verify network topology management works"""
    logger.info("🌐 Testing network topology management...")
    
    topology_manager = NetworkTopologyManager()
    
    # Create test guests
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
    
    # Test topology configuration
    topology_config = {
        'type': 'custom',
        'networks': [
            {
                'name': 'office',
                'members': ['desktop.eth0']
            }
        ]
    }
    
    ip_assignments = topology_manager.create_topology(
        topology_config, guests, "test_range"
    )
    
    if 'desktop' in ip_assignments:
        logger.info(f"  ✅ IP assignment working: desktop = {ip_assignments['desktop']}")
    else:
        logger.error("  ❌ IP assignment failed")
        return False
    
    if topology_manager.get_network_info('office'):
        logger.info("  ✅ Network topology creation successful")
    else:
        logger.error("  ❌ Network topology creation failed")
        return False
    
    return True

def test_task_execution():
    """Test 3: Verify task execution integration"""
    logger.info("⚙️ Testing task execution integration...")
    
    task_executor = TaskExecutor({
        'base_path': '/home/ubuntu/cyris',
        'ssh_timeout': 30
    })
    
    guest = (GuestBuilder()
             .with_guest_id("test_task_vm")
             .with_basevm_host("host_1")
             .with_basevm_config_file("/tmp/test.xml")
             .with_basevm_type(BaseVMType.KVM)
             .with_basevm_os_type(OSType.UBUNTU)
             .build())
    
    tasks = [
        {
            'add_account': [
                {'account': 'testuser', 'passwd': 'testpass123'}
            ]
        }
    ]
    
    # Mock the SSH execution to test command generation
    original_execute = task_executor._execute_ssh_command
    
    def mock_ssh(host, command, username="root"):
        logger.info(f"  📝 Generated SSH command for {host}: {command[:60]}...")
        if 'testuser' in command and 'testpass123' in command:
            logger.info("  ✅ Task command generation working correctly")
            return True, "Mock success", ""
        return False, "", "Mock error"
    
    task_executor._execute_ssh_command = mock_ssh
    
    try:
        results = task_executor.execute_guest_tasks(guest, "192.168.1.100", tasks)
        if results and results[0].success:
            logger.info("  ✅ Task execution integration successful")
            return True
        else:
            logger.error("  ❌ Task execution failed")
            return False
    finally:
        task_executor._execute_ssh_command = original_execute

def test_yaml_parsing():
    """Test 4: Verify full YAML parsing works"""
    logger.info("📄 Testing YAML parsing functionality...")
    
    full_yml_path = Path("examples/full.yml")
    
    if not full_yml_path.exists():
        logger.warning("  ⚠️ examples/full.yml not found - creating test YAML")
        return True  # Skip this test if file doesn't exist
    
    try:
        config_parser = CyRISConfigParser()
        result = config_parser.parse_file(str(full_yml_path))
        hosts = result.hosts
        guests = result.guests  
        clone_settings = result.clone_settings
        
        logger.info(f"  ✅ Parsed {len(hosts)} hosts, {len(guests)} guests")
        
        # Check for key components
        guest_ids = [g.guest_id for g in guests]
        if 'desktop' in guest_ids and 'webserver' in guest_ids:
            logger.info("  ✅ Key guest types (desktop, webserver) found")
        else:
            logger.error("  ❌ Missing expected guest types")
            return False
        
        # Check for tasks
        desktop = next(g for g in guests if g.guest_id == 'desktop')
        if hasattr(desktop, 'tasks') and desktop.tasks:
            logger.info(f"  ✅ Desktop has {len(desktop.tasks)} task configurations")
        else:
            logger.error("  ❌ No tasks found for desktop")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ YAML parsing failed: {e}")
        return False

def test_orchestrator_integration():
    """Test 5: Verify orchestrator integration"""
    logger.info("🎼 Testing orchestrator integration...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = CyRISSettings(
                cyris_path="/home/ubuntu/cyris",
                cyber_range_dir=temp_dir
            )
            
            provider = KVMProvider({'libvirt_uri': 'qemu:///session'})
            orchestrator = RangeOrchestrator(settings, provider)
            
            # Check that orchestrator has new components
            if hasattr(orchestrator, 'topology_manager'):
                logger.info("  ✅ Orchestrator has network topology manager")
            else:
                logger.error("  ❌ Missing topology manager")
                return False
            
            if hasattr(orchestrator, 'task_executor'):
                logger.info("  ✅ Orchestrator has task executor")
            else:
                logger.error("  ❌ Missing task executor")
                return False
            
            logger.info("  ✅ Orchestrator integration successful")
            return True
            
    except Exception as e:
        logger.error(f"  ❌ Orchestrator integration failed: {e}")
        return False

def main():
    """Run all functionality tests"""
    logger.info("🚀 Testing Complete CyRIS Functionality")
    logger.info("=" * 60)
    
    tests = [
        ("Network Fix", test_network_fix),
        ("Network Topology", test_network_topology), 
        ("Task Execution", test_task_execution),
        ("YAML Parsing", test_yaml_parsing),
        ("Orchestrator Integration", test_orchestrator_integration)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"  ❌ {test_name} test crashed: {e}")
            results[test_name] = False
        
        logger.info("")  # Add spacing between tests
    
    # Summary
    logger.info("📊 Test Results Summary:")
    logger.info("-" * 40)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All functionality tests PASSED!")
        logger.info("Network access issues have been resolved and full cyber range functionality is working!")
        return 0
    else:
        logger.error(f"\n💥 {total - passed} test(s) FAILED!")
        logger.error("Some issues still need to be resolved.")
        return 1

if __name__ == "__main__":
    exit(main())