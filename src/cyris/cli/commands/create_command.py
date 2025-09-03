"""
Create Command Handler
Handles cyber range creation logic with comprehensive validation
"""

from pathlib import Path
from typing import Optional

from .base_command import BaseCommandHandler, ValidationMixin
from cyris.cli.presentation import MessageFormatter
from ..diagnostic_messages import DiagnosticMessageFormatter, get_diagnostic_pattern_help
from ...tools.vm_diagnostics import VMDiagnostics
from ...core.progress import get_progress_tracker
from ...core.operation_tracker import is_all_operations_successful


class CreateCommandHandler(BaseCommandHandler, ValidationMixin):
    """Create command handler - Create new cyber ranges with validation"""
    
    def execute(self, description_file: Path, range_id: Optional[int] = None,
                dry_run: bool = False, network_mode: str = 'bridge',
                enable_ssh: bool = True) -> bool:
        """Execute create command with comprehensive validation and error handling"""
        try:
            # Validate inputs
            if not self.validate_file_exists(description_file):
                return False
            
            if not self.validate_yaml_file(description_file):
                return False
            
            if not self.validate_network_mode(network_mode):
                return False
            
            # Pre-creation environment checks
            if not dry_run:
                pre_check_passed = self._run_pre_creation_checks(description_file)
                if not pre_check_passed:
                    self.console.print("[yellow]⚠️ Pre-checks failed. Creation may encounter issues.[/yellow]")
                    user_input = input("Continue anyway? (y/N): ").lower()
                    if user_input not in ['y', 'yes']:
                        self.console.print("[blue]Creation cancelled by user.[/blue]")
                        return False
            
            # Display creation info
            self.console.print(f"[bold blue]Creating cyber range:[/bold blue] [cyan]{description_file}[/cyan]")
            
            if self.verbose:
                self.log_verbose(f"Configuration: {self.config}")
                self.log_verbose(f"Range ID: {range_id or 'auto-assigned'}")
                self.log_verbose(f"Network mode: {network_mode}")
                self.log_verbose(f"SSH enabled: {enable_ssh}")
            
            if dry_run:
                return self._execute_dry_run(description_file, range_id, network_mode, enable_ssh)
            else:
                return self._execute_actual_creation(description_file, range_id, network_mode, enable_ssh)
                
        except Exception as e:
            self.handle_error(e, "create")
            return False
    
    def _execute_dry_run(self, description_file: Path, range_id: Optional[int],
                        network_mode: str, enable_ssh: bool) -> bool:
        """执行干运行模式"""
        self.console.print("[bold yellow]Dry run mode - will not actually create cyber range[/bold yellow]")
        
        try:
            orchestrator, provider, singleton = self.create_orchestrator(network_mode, enable_ssh)
            if not orchestrator:
                return False
                
            with singleton:
                # For dry run, we'll validate YAML and show what would be created
                import yaml
                
                try:
                    with open(description_file, 'r') as f:
                        yaml_data = yaml.safe_load(f)
                    
                    self.console.print(f"[green]✓[/green] YAML syntax valid")
                
                    # Extract information from range description
                    hosts = []
                    guests = []
                    range_name = description_file.stem
                    
                    # Parse the YAML structure (supports both list and dict formats)
                    if isinstance(yaml_data, list):
                        for section in yaml_data:
                            if isinstance(section, dict):
                                if 'host_settings' in section:
                                    hosts.extend(section['host_settings'])
                                if 'guest_settings' in section:
                                    guests.extend(section['guest_settings'])
                                if 'clone_settings' in section:
                                    for clone in section['clone_settings']:
                                        if clone.get('range_id'):
                                            range_name = clone['range_id']
                    elif isinstance(yaml_data, dict):
                        if 'host_settings' in yaml_data:
                            hosts.extend(yaml_data['host_settings'])
                        if 'guest_settings' in yaml_data:
                            guests.extend(yaml_data['guest_settings'])
                        if 'clone_settings' in yaml_data:
                            for clone in yaml_data['clone_settings']:
                                if clone.get('range_id'):
                                    range_name = clone['range_id']
                    
                    self.console.print(f"[cyan]Range Name:[/cyan] {range_name}")
                    self.console.print(f"[cyan]Hosts:[/cyan] {len(hosts)}")
                    self.console.print(f"[cyan]Guests:[/cyan] {len(guests)}")
                    
                    # Show guest details
                    for i, guest in enumerate(guests):
                        guest_id = guest.get('id', f'guest-{i+1}')
                        self.console.print(f"  {i+1}. {guest_id}")
                        
                    return True
                except yaml.YAMLError as e:
                    self.error_display.display_error(f"YAML parsing failed: {e}")
                    return False
                except Exception as e:
                    self.error_display.display_error(f"YAML validation failed: {e}")
                    return False
                
        except Exception as e:
            self.error_display.display_error(f"Validation error: {str(e)}")
            if self.verbose:
                import traceback
                self.error_console.print(traceback.format_exc())
            return False
    
    def _execute_actual_creation(self, description_file: Path, range_id: Optional[int],
                               network_mode: str, enable_ssh: bool) -> bool:
        """执行实际的靶场创建"""
        try:
            orchestrator, provider, singleton = self.create_orchestrator(network_mode, enable_ssh)
            if not orchestrator:
                return False
                
            with singleton:
                # Let the orchestrator handle progress reporting through the progress tracker
                result_range_id = orchestrator.create_range_from_yaml(
                    description_file,
                    range_id
                )
            
            if result_range_id:
                # Get the created range details for display
                range_metadata = orchestrator.get_range(result_range_id)
                
                if range_metadata:
                    self.console.print(MessageFormatter.success(
                        f"✅ Cyber range '{range_metadata.name}' created successfully!"
                    ))
                    self.console.print(f"[cyan]Range ID:[/cyan] {result_range_id}")
                    self.console.print(f"[cyan]Status:[/cyan] {range_metadata.status.value}")
                    self.console.print(f"[cyan]Created:[/cyan] {range_metadata.created_at}")
                else:
                    self.console.print(MessageFormatter.success(
                        f"✅ Cyber range '{result_range_id}' created successfully!"
                    ))
                    self.console.print(f"[cyan]Range ID:[/cyan] {result_range_id}")
                
                # Post-creation validation
                self._run_post_creation_validation(result_range_id, orchestrator)
                
                return True
            else:
                self.console.print(MessageFormatter.error("Cyber range creation failed"))
                return False
                
        except Exception as e:
            self.error_display.display_error(f"Error creating cyber range: {str(e)}")
            if self.verbose:
                import traceback
                self.error_console.print(traceback.format_exc())
            return False
    
    def _run_pre_creation_checks(self, description_file: Path) -> bool:
        """Run environment checks before VM creation"""
        self.console.print("\n[bold blue]🔍 Pre-Creation Checks[/bold blue]")
        
        all_checks_passed = True
        
        try:
            # Check base image availability
            base_image_paths = [
                "/home/ubuntu/cyris/docs/images/basevm.qcow2",
                "/home/ubuntu/cyris/images/basevm.qcow2"
            ]
            
            base_image_found = False
            for base_path in base_image_paths:
                if Path(base_path).exists():
                    # Validate base image
                    diagnostics = VMDiagnostics()
                    result = diagnostics._validate_image_with_qemu(base_path)
                    if not result:  # No error means image is valid
                        self.console.print(f"  ✅ Base image found and valid: {base_path}")
                        base_image_found = True
                        break
                    else:
                        self.console.print(f"  ❌ Base image invalid: {base_path}")
                        self.console.print(f"     {result.message}")
                        all_checks_passed = False
            
            if not base_image_found:
                self.console.print("  ❌ No valid base image found")
                self.console.print("     💡 Ensure basevm.qcow2 exists and is valid")
                all_checks_passed = False
            
            # Check cloud-init.iso availability
            cloud_init_paths = [
                "/home/ubuntu/cyris/docs/images/cloud-init.iso",
                "/home/ubuntu/cyris/images/cloud-init.iso"
            ]
            
            cloud_init_found = any(Path(p).exists() for p in cloud_init_paths)
            if cloud_init_found:
                self.console.print("  ✅ cloud-init.iso found")
            else:
                self.console.print("  ⚠️ cloud-init.iso not found")
                self.console.print("     💡 VMs may fail to initialize properly")
                help_info = get_diagnostic_pattern_help("missing_cloud_init")
                self.console.print(f"     💡 {help_info['quick_fix']}")
                all_checks_passed = False
            
            # Check libvirt connectivity
            try:
                import subprocess
                result = subprocess.run(['virsh', 'version'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    self.console.print("  ✅ libvirt connectivity confirmed")
                else:
                    self.console.print("  ❌ libvirt not accessible")
                    all_checks_passed = False
            except:
                self.console.print("  ❌ libvirt check failed")
                all_checks_passed = False
            
            # Check network configuration
            try:
                result = subprocess.run(['virsh', 'net-list', '--active'], capture_output=True, timeout=5)
                if result.returncode == 0 and 'default' in result.stdout:
                    self.console.print("  ✅ Default network available")
                else:
                    self.console.print("  ⚠️ Default network may not be active")
                    all_checks_passed = False
            except:
                self.console.print("  ⚠️ Network configuration check failed")
                all_checks_passed = False
            
        except Exception as e:
            self.console.print(f"  ❌ Pre-check failed: {str(e)}")
            all_checks_passed = False
        
        if all_checks_passed:
            self.console.print("  🎉 All pre-checks passed!")
        
        return all_checks_passed
    
    def _run_post_creation_validation(self, range_id: str, orchestrator) -> None:
        """Validate VM health after creation"""
        self.console.print("\n[bold blue]🔍 Post-Creation Validation[/bold blue]")
        
        try:
            # Wait a moment for VMs to start up
            self.console.print("  ⏳ Waiting for VMs to initialize...")
            import time
            time.sleep(5)
            
            # Get range resources
            resources = orchestrator.get_range_resources(range_id)
            if not resources or not resources.get('guests'):
                self.console.print("  ❌ No VMs found in created range")
                return
            
            vm_issues_found = False
            diagnostics = VMDiagnostics()
            
            for vm_name in resources['guests']:
                try:
                    # Quick health check
                    health_results = diagnostics.check_cloud_init_config(vm_name)
                    health_results.extend(diagnostics.check_vm_image_health(vm_name))
                    
                    # Check for critical issues
                    critical_issues = [r for r in health_results if r.level.value in ['error', 'critical']]
                    
                    if critical_issues:
                        self.console.print(f"  ❌ {vm_name}: {len(critical_issues)} issue(s) detected")
                        for issue in critical_issues[:2]:  # Show top 2 issues
                            self.console.print(f"     • {issue.message}")
                            if issue.suggestion:
                                self.console.print(f"       💡 {issue.suggestion}")
                        vm_issues_found = True
                    else:
                        self.console.print(f"  ✅ {vm_name}: Initial validation passed")
                        
                except Exception as e:
                    self.console.print(f"  ⚠️ {vm_name}: Validation check failed - {str(e)}")
                    vm_issues_found = True
            
            if vm_issues_found:
                self.console.print("\n  💡 Tip: Use 'cyris status {range_id} --verbose' for detailed diagnostics".format(range_id=range_id))
            else:
                self.console.print("  🎉 All VMs appear healthy!")
                
        except Exception as e:
            self.console.print(f"  ⚠️ Post-validation failed: {str(e)}")