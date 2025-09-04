#!/usr/bin/env python3
"""
Final verification script to confirm the parsing hang issue is resolved
"""
import sys
import time
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Add cyris to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_configuration_parsing():
    """Test that configuration parsing works without hanging"""
    print("🔍 Testing Configuration Parsing Performance...")
    
    try:
        from cyris.config.parser import CyRISConfigParser
        
        parser = CyRISConfigParser()
        yaml_file = Path("test-kvm-auto.yml")
        
        # Time the parsing operation
        start_time = time.time()
        logger.info("Starting configuration parsing...")
        
        config = parser.parse_file(yaml_file)
        
        end_time = time.time()
        parse_time = end_time - start_time
        
        logger.info(f"Configuration parsed successfully in {parse_time:.3f} seconds")
        print(f"✅ Parse time: {parse_time:.3f}s (should be < 1s)")
        print(f"✅ Results: {len(config.hosts)} hosts, {len(config.guests)} guests")
        
        # Verify guest details
        if len(config.guests) > 0:
            guest = config.guests[0]
            print(f"✅ Guest: {guest.guest_id}, type: {guest.basevm_type}")
            print(f"✅ Image: {guest.image_name}, OS: {guest.basevm_os_type}")
        
        return parse_time < 5.0  # Should be very fast now
        
    except Exception as e:
        logger.error(f"❌ Configuration parsing failed: {e}")
        return False

def test_guest_validation():
    """Test that Guest validation works correctly"""
    print("\n🔍 Testing Guest Entity Validation...")
    
    try:
        from cyris.domain.entities.guest import Guest, BaseVMType, OSType
        
        # Test creating a Guest entity directly
        start_time = time.time()
        
        guest = Guest(
            guest_id="test-validation",
            basevm_type=BaseVMType.KVM_AUTO,
            image_name="opensuse-tumbleweed",
            vcpus=2,
            memory=2048,
            disk_size="20G"
        )
        
        end_time = time.time()
        validation_time = end_time - start_time
        
        logger.info(f"Guest validation completed in {validation_time:.3f} seconds")
        print(f"✅ Validation time: {validation_time:.3f}s (should be < 0.1s)")
        print(f"✅ Guest created: {guest.guest_id}")
        print(f"✅ OS type derived: {guest.basevm_os_type}")
        
        return validation_time < 1.0
        
    except Exception as e:
        logger.error(f"❌ Guest validation failed: {e}")
        return False

def test_dry_run():
    """Test that dry run works correctly"""
    print("\n🔍 Testing Dry Run Execution...")
    
    try:
        import subprocess
        
        # Test dry run
        start_time = time.time()
        
        result = subprocess.run([
            'bash', '-c',
            'source .venv/bin/activate && ./cyris create test-kvm-auto.yml --dry-run'
        ], capture_output=True, text=True, timeout=30)
        
        end_time = time.time()
        dry_run_time = end_time - start_time
        
        if result.returncode == 0:
            logger.info(f"Dry run completed successfully in {dry_run_time:.3f} seconds")
            print(f"✅ Dry run time: {dry_run_time:.3f}s")
            print("✅ Dry run output:")
            for line in result.stdout.split('\n'):
                if line.strip():
                    print(f"   {line}")
            return True
        else:
            logger.error(f"Dry run failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Dry run timed out - still hanging!")
        return False
    except Exception as e:
        logger.error(f"❌ Dry run test failed: {e}")
        return False

def main():
    """Run all verification tests"""
    print("🚀 Final Verification: Parsing Hang Fix")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Configuration parsing performance
    if not test_configuration_parsing():
        all_passed = False
        
    # Test 2: Guest validation performance  
    if not test_guest_validation():
        all_passed = False
        
    # Test 3: Dry run execution
    if not test_dry_run():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Configuration parsing hang issue RESOLVED")
        print("✅ The cyris create command should now work normally")
    else:
        print("❌ SOME TESTS FAILED")
        print("⚠️ Additional issues may need to be addressed")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)