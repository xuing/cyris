#!/usr/bin/env python3
"""
Debug script to identify parsing hang location
"""
import logging
import sys
from pathlib import Path

# Set up detailed debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_parser.log')
    ]
)

# Add cyris to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_yaml_parsing():
    """Test YAML parsing with detailed debugging"""
    print("=" * 80)
    print("STARTING YAML PARSING DEBUG TEST")
    print("=" * 80)
    
    try:
        from cyris.config.parser import CyRISConfigParser
        print("✅ Successfully imported CyRISConfigParser")
        
        parser = CyRISConfigParser()
        print("✅ Successfully created parser instance")
        
        yaml_file = Path("test-kvm-auto.yml")
        if not yaml_file.exists():
            print(f"❌ YAML file not found: {yaml_file}")
            return False
            
        print(f"✅ YAML file found: {yaml_file}")
        print(f"📄 File size: {yaml_file.stat().st_size} bytes")
        
        # Show file content
        print("\n" + "=" * 40)
        print("YAML FILE CONTENT:")
        print("=" * 40)
        with open(yaml_file, 'r') as f:
            content = f.read()
            print(content)
        print("=" * 40)
        
        print("\n🔍 About to call parser.parse_file()...")
        print("⏰ This is where it might hang. Watching for logs...")
        
        # This is where it hangs
        config = parser.parse_file(yaml_file)
        
        print("✅ parse_file() completed successfully!")
        print(f"📊 Results: {len(config.hosts)} hosts, {len(config.guests)} guests")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        print(f"🔍 Traceback:\n{traceback.format_exc()}")
        return False

def test_minimal_yaml():
    """Test with minimal YAML to isolate issue"""
    print("\n" + "=" * 80)
    print("TESTING MINIMAL YAML")
    print("=" * 80)
    
    # Create minimal test YAML
    minimal_yaml = """---
- host_settings:
  - id: localhost
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: ubuntu
"""
    
    minimal_file = Path("test-minimal.yml")
    with open(minimal_file, 'w') as f:
        f.write(minimal_yaml)
        
    try:
        from cyris.config.parser import CyRISConfigParser
        parser = CyRISConfigParser()
        
        print("🔍 Testing minimal YAML (hosts only)...")
        config = parser.parse_file(minimal_file)
        print(f"✅ Minimal YAML parsed successfully: {len(config.hosts)} hosts")
        
        # Clean up
        minimal_file.unlink()
        return True
        
    except Exception as e:
        print(f"❌ Minimal YAML failed: {e}")
        minimal_file.unlink(missing_ok=True)
        return False

def test_guest_only_yaml():
    """Test with guest-only YAML"""
    print("\n" + "=" * 80)
    print("TESTING GUEST-ONLY YAML")
    print("=" * 80)
    
    # Create guest-only test YAML
    guest_yaml = """---
- guest_settings:
  - id: test-guest
    basevm_type: kvm-auto
    image_name: opensuse-tumbleweed
    vcpus: 2
    memory: 2048
    disk_size: 20G
"""
    
    guest_file = Path("test-guest.yml")
    with open(guest_file, 'w') as f:
        f.write(guest_yaml)
        
    try:
        from cyris.config.parser import CyRISConfigParser
        parser = CyRISConfigParser()
        
        print("🔍 Testing guest-only YAML...")
        config = parser.parse_file(guest_file)
        print(f"✅ Guest YAML parsed successfully: {len(config.guests)} guests")
        
        # Clean up
        guest_file.unlink()
        return True
        
    except Exception as e:
        print(f"❌ Guest YAML failed: {e}")
        import traceback
        print(f"🔍 Traceback:\n{traceback.format_exc()}")
        guest_file.unlink(missing_ok=True)
        return False

if __name__ == "__main__":
    print("🚀 Starting CyRIS Parser Debug Session")
    print(f"📂 Working directory: {Path.cwd()}")
    print(f"🐍 Python path: {sys.executable}")
    
    # Test sequence
    success = True
    
    # Step 1: Test minimal YAML (hosts only)
    if not test_minimal_yaml():
        success = False
        print("❌ Minimal YAML test failed - basic parsing issue")
    
    # Step 2: Test guest-only YAML 
    if success and not test_guest_only_yaml():
        success = False
        print("❌ Guest YAML test failed - issue in guest parsing")
    
    # Step 3: Test full YAML
    if success and not test_yaml_parsing():
        success = False
        print("❌ Full YAML test failed - complex interaction issue")
    
    if success:
        print("\n🎉 ALL TESTS PASSED - No parsing hang detected!")
    else:
        print("\n💥 TESTS FAILED - Check logs for details")
        
    print(f"\n📝 Debug log saved to: {Path.cwd() / 'debug_parser.log'}")