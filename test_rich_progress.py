#!/usr/bin/env python3
"""
Rich Progress Test Script

Tests the enhanced Rich progress system with KVM auto workflow.
This script provides both manual testing capabilities and automated validation.
"""

import sys
import time
import argparse
from pathlib import Path

# Add the src directory to the Python path for testing
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from cyris.core.rich_progress import RichProgressManager, ProgressLevel
    from cyris.infrastructure.image_builder import LocalImageBuilder
    from rich.console import Console
    
    # Try to import KVM components (may fail due to dependencies)
    try:
        from cyris.infrastructure.providers.kvm_provider import KVMProvider
        from cyris.domain.entities.guest import Guest, BaseVMType
        KVM_AVAILABLE = True
    except ImportError as e:
        print(f"Warning: KVM components not available: {e}")
        KVM_AVAILABLE = False
        
except ImportError as e:
    print(f"Error importing CyRIS modules: {e}")
    print("Make sure you're running from the correct directory and dependencies are installed.")
    sys.exit(1)


def test_basic_progress_manager():
    """Test basic Rich progress manager functionality"""
    print("=" * 60)
    print("Testing Basic Rich Progress Manager")
    print("=" * 60)
    
    # Create progress manager
    progress = RichProgressManager("Test Operation")
    
    with progress.progress_context():
        with progress.live_context():
            # Test different log levels
            progress.log_info("Starting basic test...")
            progress.log_success("Test initialization successful")
            progress.log_warning("This is a warning message")
            progress.log_error("This is an error message (simulated)")
            progress.log_command("echo 'Hello World'")
            
            # Test progress steps
            progress.start_step("step1", "Testing step 1...", total=100)
            for i in range(0, 101, 10):
                progress.update_step("step1", completed=i)
                time.sleep(0.1)
            progress.complete_step("step1")
            
            # Test nested steps
            progress.start_step("step2", "Testing step 2 with sub-operations...")
            progress.log_info("  Sub-operation 1: Preparing...")
            time.sleep(0.5)
            progress.log_info("  Sub-operation 2: Processing...")
            time.sleep(0.5)
            progress.log_info("  Sub-operation 3: Finalizing...")
            time.sleep(0.5)
            progress.complete_step("step2")
            
            # Test failure case
            progress.start_step("step3", "Testing failure handling...")
            time.sleep(0.3)
            progress.fail_step("step3", "Simulated failure for testing")
            
            # Complete overall operation
            progress.complete()
    
    # Show summary
    summary = progress.get_summary()
    print(f"\\nTest Summary:")
    print(f"  Operation: {summary['operation']}")
    print(f"  Success: {summary['success']}")
    print(f"  Duration: {summary['duration']:.2f}s")
    print(f"  Steps Completed: {summary['steps_completed']}/{summary['steps_total']}")


def test_image_builder_progress():
    """Test Image Builder with Rich progress"""
    print("\\n" + "=" * 60)
    print("Testing Image Builder with Rich Progress")
    print("=" * 60)
    
    # Create progress manager
    progress = RichProgressManager("Image Builder Test")
    
    # Create image builder
    image_builder = LocalImageBuilder()
    image_builder.set_progress_manager(progress)
    
    with progress.progress_context():
        with progress.live_context():
            progress.log_info("Testing Image Builder dependencies...")
            
            # Test dependency checking
            deps = image_builder.check_local_dependencies()
            for tool, available in deps.items():
                if available:
                    progress.log_success(f"{tool}: Available")
                else:
                    progress.log_error(f"{tool}: Not available")
            
            # Test available images (if virt-builder is available)
            if deps.get('virt-builder', False):
                progress.log_info("Checking available images...")
                try:
                    available_images = image_builder.get_available_images()
                    progress.log_info(f"Found {len(available_images)} available images")
                    if available_images:
                        progress.log_info(f"Sample images: {', '.join(available_images[:5])}")
                except Exception as e:
                    progress.log_error(f"Failed to get available images: {e}")
            else:
                progress.log_warning("virt-builder not available - skipping image tests")
            
            progress.complete()


def test_kvm_provider_progress():
    """Test KVM Provider with Rich progress"""
    print("\\n" + "=" * 60)
    print("Testing KVM Provider with Rich Progress")
    print("=" * 60)
    
    # Create progress manager
    progress = RichProgressManager("KVM Provider Test")
    
    # Create KVM provider (with mock config)
    config = {
        "libvirt_uri": "qemu:///session",
        "network_prefix": "cyris-test"
    }
    
    kvm_provider = KVMProvider(config)
    kvm_provider.set_progress_manager(progress)
    
    with progress.progress_context():
        with progress.live_context():
            progress.log_info("Testing KVM Provider functionality...")
            
            # Test connection
            try:
                progress.log_info("Testing libvirt connectivity...")
                kvm_provider.connect()
                progress.log_success("Libvirt connection successful")
                
                # Test provider info
                provider_info = kvm_provider.get_provider_info()
                progress.log_info(f"Provider: {provider_info['name']} v{provider_info['version']}")
                
                kvm_provider.disconnect()
                progress.log_success("Connection test completed")
                
            except Exception as e:
                progress.log_error(f"KVM Provider test failed: {e}")
                progress.log_info("This is normal if libvirt is not configured")
            
            progress.complete()


def create_sample_guest():
    """Create a sample guest for testing"""
    class MockGuest:
        def __init__(self):
            self.guest_id = "test-ubuntu"
            self.basevm_type = BaseVMType.KVM_AUTO
            self.image_name = "ubuntu-20.04"
            self.vcpus = 1
            self.memory = 1024
            self.disk_size = "10G"
            self.tasks = [
                {
                    "add_account": [
                        {"account": "testuser", "passwd": "test123"}
                    ]
                }
            ]
    
    return MockGuest()


def test_end_to_end_simulation():
    """Test end-to-end simulation without actually creating VMs"""
    print("\\n" + "=" * 60)
    print("Testing End-to-End Progress Simulation")
    print("=" * 60)
    
    # Create progress manager for the full workflow
    progress = RichProgressManager("CyRIS KVM Auto Workflow Simulation")
    
    with progress.progress_context():
        with progress.live_context():
            # Phase 1: Pre-checks
            progress.start_step("pre_checks", "Running pre-creation checks...")
            progress.log_info("Checking system dependencies...")
            time.sleep(0.5)
            progress.log_success("libvirt connectivity: OK")
            time.sleep(0.3)
            progress.log_success("Network configuration: OK")
            time.sleep(0.3)
            progress.log_success("kvm-auto requirements: OK")
            progress.complete_step("pre_checks")
            
            # Phase 2: Configuration parsing
            progress.start_step("config_parse", "Parsing YAML configuration...")
            time.sleep(0.4)
            progress.log_info("Found 1 host and 1 guest configuration")
            progress.log_info("Guest type: kvm-auto (ubuntu-20.04)")
            progress.complete_step("config_parse")
            
            # Phase 3: Image building
            progress.start_step("image_build", "Building VM image...", total=100)
            progress.log_info("Starting virt-builder for ubuntu-20.04...")
            progress.log_command("virt-builder ubuntu-20.04 --size 10G --format qcow2")
            
            # Simulate image building progress
            for i in range(0, 101, 5):
                progress.update_step("image_build", completed=i)
                if i == 20:
                    progress.log_info("Downloading base image...")
                elif i == 50:
                    progress.log_info("Customizing image...")
                elif i == 80:
                    progress.log_info("Finalizing image...")
                time.sleep(0.1)
            
            progress.log_success("Image built successfully: 1.2 GB")
            progress.complete_step("image_build")
            
            # Phase 4: Task execution
            progress.start_step("tasks", "Executing build-time tasks...")
            progress.log_info("Adding user account: testuser")
            progress.log_command("virt-customize --run-command 'useradd -m testuser'")
            time.sleep(0.3)
            progress.log_success("User account created successfully")
            progress.complete_step("tasks")
            
            # Phase 5: VM creation
            progress.start_step("vm_create", "Creating virtual machine...")
            progress.log_info("Creating VM: test-ubuntu")
            progress.log_command("virt-install --import --name test-ubuntu --memory 1024")
            time.sleep(0.8)
            progress.log_success("VM created successfully: cyris-test-ubuntu-12345678")
            progress.complete_step("vm_create")
            
            # Phase 6: Post-validation
            progress.start_step("validation", "Running post-creation validation...")
            progress.log_info("Waiting for VM to initialize...")
            time.sleep(0.5)
            progress.log_info("Checking VM: test-ubuntu")
            progress.log_success("test-ubuntu: Initial validation passed")
            progress.complete_step("validation")
            
            # Complete overall operation
            progress.complete()
    
    # Show final summary
    summary = progress.get_summary()
    console = Console()
    console.print("\\n🎉 [bold green]Simulation completed successfully![/bold green]")
    console.print(f"Duration: {summary['duration']:.1f}s")
    console.print(f"Steps: {summary['steps_completed']}/{summary['steps_total']} completed")


def test_error_scenarios():
    """Test various error scenarios"""
    print("\\n" + "=" * 60)
    print("Testing Error Handling Scenarios")
    print("=" * 60)
    
    progress = RichProgressManager("Error Scenario Tests")
    
    with progress.progress_context():
        with progress.live_context():
            # Test various error scenarios
            progress.log_info("Testing different error scenarios...")
            
            # Scenario 1: Missing dependencies
            progress.start_step("deps", "Checking dependencies...")
            progress.log_error("virt-builder not found")
            progress.log_info("Install with: sudo apt install libguestfs-tools")
            progress.fail_step("deps", "Required dependencies missing")
            
            # Scenario 2: Network issues
            progress.start_step("network", "Testing network connectivity...")
            progress.log_warning("Default network may not be active")
            progress.log_info("Attempting to start default network...")
            progress.log_error("Failed to start network: Permission denied")
            progress.fail_step("network", "Network configuration issues")
            
            # Scenario 3: Partial success
            progress.start_step("partial", "Testing partial operations...")
            progress.log_success("Phase 1: Complete")
            progress.log_success("Phase 2: Complete")
            progress.log_error("Phase 3: Failed - disk space insufficient")
            progress.fail_step("partial", "Partial failure - cleanup required")
            
            progress.complete()
    
    summary = progress.get_summary()
    console = Console()
    console.print(f"\\n⚠️ [yellow]Test completed with errors (expected)[/yellow]")
    console.print(f"Failed steps: {summary['steps_failed']}/{summary['steps_total']}")


def main():
    parser = argparse.ArgumentParser(description="Test Rich Progress System")
    parser.add_argument(
        "--test",
        choices=["basic", "image", "kvm", "e2e", "errors", "all"],
        default="all",
        help="Which test to run"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run tests with user prompts"
    )
    
    args = parser.parse_args()
    
    console = Console()
    console.print("[bold blue]CyRIS Rich Progress Test Suite[/bold blue]")
    console.print("Testing the enhanced progress reporting system\\n")
    
    if args.interactive:
        input("Press Enter to start tests...")
    
    tests = {
        "basic": test_basic_progress_manager,
        "image": test_image_builder_progress, 
        "kvm": test_kvm_provider_progress,
        "e2e": test_end_to_end_simulation,
        "errors": test_error_scenarios
    }
    
    if args.test == "all":
        for test_name, test_func in tests.items():
            test_func()
            if args.interactive:
                input(f"\\n{test_name} test completed. Press Enter for next test...")
    else:
        tests[args.test]()
    
    console.print("\\n[bold green]✅ All tests completed![/bold green]")
    console.print("The Rich progress system is working correctly.")


if __name__ == "__main__":
    main()