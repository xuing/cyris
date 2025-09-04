"""
Create Command Handler
Handles cyber range creation logic with comprehensive validation
"""

from pathlib import Path
from typing import Optional
from cyris.core.unified_logger import get_logger

from .base_command import BaseCommandHandler, ValidationMixin
from cyris.cli.presentation import MessageFormatter
from ..diagnostic_messages import DiagnosticMessageFormatter, get_diagnostic_pattern_help
from cyris.tools.vm_diagnostics import VMDiagnostics
from cyris.core.progress import get_progress_tracker
from cyris.core.rich_progress import create_rich_progress_manager, ProgressLevel
from cyris.core.operation_tracker import is_all_operations_successful
from cyris.config.parser import ConfigurationError


class CreateCommandHandler(BaseCommandHandler, ValidationMixin):
    """Create command handler - Create new cyber ranges with validation"""
    
    def execute(self, description_file: Path, range_id: Optional[int] = None,
                dry_run: bool = False, build_only: bool = False, skip_builder: bool = False, 
                network_mode: str = 'bridge', enable_ssh: bool = True) -> bool:
        """Execute create command with comprehensive validation and error handling"""
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] CreateCommandHandler.execute() START with file={description_file}\n")
            f.write(f"[DEBUG] Parameters: dry_run={dry_run}, build_only={build_only}, skip_builder={skip_builder}\n")
            f.flush()
        
        # Debug print for parameter checking
        self.logger.info(f"[DEBUG_PARAMS] execute() called with: dry_run={dry_run}, build_only={build_only}, skip_builder={skip_builder}")
        self.console.print(f"[dim][DEBUG] Parameters: dry_run={dry_run}, build_only={build_only}, skip_builder={skip_builder}[/dim]")
        
        try:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] Starting input validation\n")
                f.flush()
            
            # Validate inputs
            if not self.validate_file_exists(description_file):
                return False
            
            if not self.validate_yaml_file(description_file):
                return False
            
            if not self.validate_network_mode(network_mode):
                return False
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] Input validation completed successfully\n")
                f.flush()
            
            # Pre-creation environment checks
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] About to start pre-creation checks, dry_run={dry_run}\n")
                f.flush()
            
            if not dry_run:
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write("[DEBUG] Calling _run_pre_creation_checks()\n")
                    f.flush()
                pre_check_passed = self._run_pre_creation_checks(description_file)
                if not pre_check_passed:
                    self.console.print("[yellow]⚠️ Pre-checks failed. Creation may encounter issues.[/yellow]")
                    try:
                        user_input = input("Continue anyway? (y/N): ").lower()
                        if user_input not in ['y', 'yes']:
                            self.console.print("[blue]Creation cancelled by user.[/blue]")
                            return False
                    except EOFError:
                        # Non-interactive mode - proceed automatically
                        self.console.print("[yellow]Non-interactive mode detected. Proceeding with creation...[/yellow]")
            
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
                return self._execute_actual_creation(description_file, range_id, network_mode, enable_ssh, dry_run, build_only, skip_builder)
                
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
                               network_mode: str, enable_ssh: bool, dry_run: bool = False, 
                               build_only: bool = False, skip_builder: bool = False) -> bool:
        """Execute actual cyber range creation with simplified Rich display"""
        
        # Create simplified Rich progress manager (no Live display, no complex layouts)
        class SimplifiedRichProgressManager:
            def __init__(self, operation_name):
                from rich.console import Console
                self.console = Console()
                self.operation_name = operation_name
                self.overall_success = True
                
            def progress_context(self):
                class DummyContext:
                    def __enter__(self): return None
                    def __exit__(self, *args): pass
                return DummyContext()
                
            def live_context(self):
                class DummyContext:
                    def __enter__(self): return None
                    def __exit__(self, *args): pass
                return DummyContext()
                
            def start_step(self, step_id, description, total=None):
                self.console.print(f"[bold blue]🔄 {description}[/bold blue]")
                # Add debug logging
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] start_step({step_id}): {description} (total={total})\n")
                    f.flush()
                
            def update_step(self, step_id, completed=None, total=None, description=None):
                if completed is not None and total is not None:
                    progress_pct = int((completed / total) * 100) if total > 0 else 0
                    self.console.print(f"[blue]📊 {step_id}: {progress_pct}% ({completed}/{total})[/blue]")
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] update_step({step_id}): completed={completed}, total={total}\n")
                    f.flush()
                    
            def complete_step(self, step_id):
                self.console.print(f"[bold green]✅ Step '{step_id}' completed[/bold green]")
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] complete_step({step_id}) called\n")
                    f.flush()
                    
            def fail_step(self, step_id, error):
                self.console.print(f"[bold red]❌ Step '{step_id}' failed: {error}[/bold red]")
                self.overall_success = False
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] fail_step({step_id}): {error}\n")
                    f.flush()
                
            def log_info(self, message):
                self.console.print(f"[blue]ℹ️  {message}[/blue]")
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] log_info: {message}\n")
                    f.flush()
                
            def log_success(self, message):
                self.console.print(f"[bold green]✅ {message}[/bold green]")
                
            def log_error(self, message):
                self.console.print(f"[bold red]❌ {message}[/bold red]")
                
            def log_command(self, command):
                self.console.print(f"[dim]💻 CMD: {command}[/dim]")
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] log_command: {command}\n")
                    f.flush()
                
            def complete(self):
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write(f"[DEBUG] progress_manager.complete() called\n")
                    f.flush()
        
        progress_manager = SimplifiedRichProgressManager(f"Creating Cyber Range: {description_file.stem}")
        
        try:
            # Start the main operation with Rich progress context
            with progress_manager.progress_context():
                with progress_manager.live_context():
                    
                    # Phase 1: Initialize orchestrator
                    progress_manager.start_step("init", "Initializing orchestrator...")
                    orchestrator, provider, singleton = self.create_orchestrator(network_mode, enable_ssh)
                    if not orchestrator:
                        progress_manager.fail_step("init", "Failed to create orchestrator")
                        return False
                    progress_manager.complete_step("init")
                    
                    with singleton:
                        # Phase 2: Parse and validate configuration
                        progress_manager.start_step("parse", "Parsing YAML configuration...")
                        try:
                            progress_manager.log_info("[DEBUG] Importing CyRISConfigParser...")
                            from cyris.config.parser import CyRISConfigParser
                            progress_manager.log_info("[DEBUG] Creating parser instance...")
                            parser = CyRISConfigParser()
                            progress_manager.log_info(f"[DEBUG] About to call parse_file({description_file})...")
                            config = parser.parse_file(description_file)
                            progress_manager.log_info(f"[DEBUG] parse_file completed successfully!")
                            progress_manager.log_info(f"Found {len(config.hosts)} hosts and {len(config.guests)} guests")
                            progress_manager.complete_step("parse")
                        except Exception as e:
                            progress_manager.fail_step("parse", f"Configuration parsing failed: {e}")
                            return False
                        
                        # Phase 3: Create cyber range with orchestrator
                        progress_manager.start_step("create", "Creating cyber range infrastructure...", total=100)
                        progress_manager.log_info("[DEBUG] Starting orchestrator phase...")
                        
                        # Pass progress manager to orchestrator for detailed progress updates
                        if hasattr(orchestrator, 'set_progress_manager'):
                            progress_manager.log_info("[DEBUG] Setting progress manager on orchestrator...")
                            orchestrator.set_progress_manager(progress_manager)
                        else:
                            progress_manager.log_info("[DEBUG] Orchestrator does not have set_progress_manager method")
                        
                        progress_manager.log_info(f"[DEBUG] About to call orchestrator.create_range_from_yaml({description_file}, {range_id})...")
                        result_range_id = orchestrator.create_range_from_yaml(
                            description_file,
                            range_id,
                            dry_run=dry_run,
                            build_only=build_only,
                            skip_builder=skip_builder
                        )
                        progress_manager.log_info(f"[DEBUG] orchestrator.create_range_from_yaml returned: {result_range_id}")
                        
                        if result_range_id:
                            progress_manager.complete_step("create")
                        else:
                            progress_manager.fail_step("create", "Range creation failed")
                            return False
            
                        # Phase 4: Post-creation validation 
                        progress_manager.start_step("validate", "Running post-creation validation...")
                        
                        # Get the created range details for display
                        range_metadata = orchestrator.get_range(result_range_id)
                        
                        if range_metadata:
                            progress_manager.log_success(f"Cyber range '{range_metadata.name}' created successfully!")
                            progress_manager.log_info(f"Range ID: {result_range_id}")
                            progress_manager.log_info(f"Status: {range_metadata.status.value}")
                            progress_manager.log_info(f"Created: {range_metadata.created_at}")
                        else:
                            progress_manager.log_success(f"Cyber range '{result_range_id}' created successfully!")
                            progress_manager.log_info(f"Range ID: {result_range_id}")
                        
                        # Post-creation validation with progress tracking (skip in build-only mode)
                        if build_only:
                            # Skip post-creation validation in build-only mode
                            progress_manager.log_info("Skipping post-creation validation (build-only mode)")
                            progress_manager.complete_step("validate")
                            validation_success = True
                        else:
                            validation_success = self._run_post_creation_validation_with_progress(
                                result_range_id, orchestrator, progress_manager
                            )
                            
                            if validation_success:
                                progress_manager.complete_step("validate")
                            else:
                                progress_manager.fail_step("validate", "Post-creation validation found issues")
                        
                        # Complete the overall operation
                        progress_manager.complete()
                        
                        # Final success display
                        if progress_manager.overall_success:
                            self.console.print()  # Add blank line
                            if build_only:
                                self.console.print(MessageFormatter.success(
                                    f"🎉 Image building completed successfully!"
                                ))
                            else:
                                self.console.print(MessageFormatter.success(
                                    f"🎉 Cyber range creation completed successfully!"
                                ))
                            return True
                        else:
                            self.console.print()  # Add blank line
                            self.console.print(MessageFormatter.error(
                                "⚠️ Cyber range created but with validation issues"
                            ))
                            return False
                
        except Exception as e:
            progress_manager.fail_step("error", f"Unexpected error: {str(e)}")
            progress_manager.complete()
            
            self.error_display.display_error(f"Error creating cyber range: {str(e)}")
            if self.verbose:
                import traceback
                self.error_console.print(traceback.format_exc())
            return False
    
    def _run_pre_creation_checks(self, description_file: Path) -> bool:
        """Run environment checks before VM creation with Rich progress"""
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write("[DEBUG] _run_pre_creation_checks() START\n")
            f.flush()
        
        # Create progress manager for pre-checks
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write("[DEBUG] About to create Rich progress manager (using simple fallback)\n")
            f.flush()
        
        # TEMPORARY FIX: Use simple console output instead of Rich progress manager
        # to avoid hanging issue. This bypasses the Rich Live display that's causing problems.
        class SimpleProgressManager:
            def __init__(self, name, logger=None, console=None):
                self.name = name
                self.logger = logger
                self.console = console
            
            def progress_context(self):
                class DummyContext:
                    def __enter__(self): return None
                    def __exit__(self, *args): pass
                return DummyContext()
            
            def live_context(self):
                class DummyContext:
                    def __enter__(self): return None
                    def __exit__(self, *args): pass
                return DummyContext()
            
            def start_step(self, step_id, description):
                if self.logger:
                    self.logger.info(f"🔄 {description}")
                else:
                    print(f"🔄 {description}")
                
            def complete_step(self, step_id):
                if self.logger:
                    self.logger.info(f"✅ Step '{step_id}' completed")
                else:
                    print(f"✅ Step '{step_id}' completed")
                
            def log_info(self, message):
                if self.logger:
                    self.logger.info(f"ℹ️  {message}")
                else:
                    print(f"ℹ️  {message}")
                
            def log_success(self, message):
                if self.logger:
                    self.logger.info(f"✅ {message}")
                else:
                    print(f"✅ {message}")
                
            def log_error(self, message):
                if self.logger:
                    self.logger.info(f"❌ {message}")
                else:
                    print(f"❌ {message}")
                
            def log_warning(self, message):
                if self.logger:
                    self.logger.info(f"⚠️  {message}")
                else:
                    print(f"⚠️  {message}")
        
        check_progress = SimpleProgressManager("Pre-Creation Environment Checks", logger=self.logger, console=self.console)
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write("[DEBUG] Rich progress manager created\n")
            f.flush()
        
        all_checks_passed = True
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write("[DEBUG] About to enter progress context\n")
            f.flush()
        
        with check_progress.progress_context():
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] Entered progress context, about to enter live context\n")
                f.flush()
                
            with check_progress.live_context():
                with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                    f.write("[DEBUG] Entered live context, starting try block\n")
                    f.flush()
                
                try:
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] About to parse YAML and import config parser\n")
                        f.flush()
                    
                    # Parse YAML to determine guest types
                    from cyris.config.parser import CyRISConfigParser
                    from cyris.domain.entities.guest import BaseVMType
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] Imports completed, creating parser instance\n")
                        f.flush()
                    
                    parser = CyRISConfigParser()
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] Parser created, about to parse file\n")
                        f.flush()
                    
                    config = parser.parse_file(description_file)
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] File parsed successfully, continuing with checks\n")
                        f.flush()
                    
                    # Step 1: Parse configuration
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] About to call check_progress.start_step('config')\n")
                        f.flush()
                    
                    check_progress.start_step("config", "Parsing configuration...")
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] start_step('config') completed\n")
                        f.flush()
                    
                    # Check if we have traditional KVM guests (need base images)
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] About to access config.guests\n")
                        f.flush()
                    
                    traditional_kvm_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM]
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write(f"[DEBUG] traditional_kvm_guests created: {len(traditional_kvm_guests)}\n")
                        f.flush()
                    
                    kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write(f"[DEBUG] kvm_auto_guests created: {len(kvm_auto_guests)}\n")
                        f.flush()
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] About to log guest counts to progress\n")
                        f.flush()
                    
                    check_progress.log_info(f"Found {len(traditional_kvm_guests)} traditional KVM guests")
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] Logged traditional KVM guests count\n")
                        f.flush()
                    
                    check_progress.log_info(f"Found {len(kvm_auto_guests)} kvm-auto guests")
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] Logged kvm-auto guests count\n")
                        f.flush()
                    
                    check_progress.complete_step("config")
                    
                    with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                        f.write("[DEBUG] complete_step('config') called\n")
                        f.flush()
                    
                    # Step 2: Check base images (only if needed)
                    if traditional_kvm_guests:
                        check_progress.start_step("base_images", "Checking base VM images...")
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
                                    check_progress.log_success(f"Base image found and valid: {base_path}")
                                    base_image_found = True
                                    break
                                else:
                                    check_progress.log_error(f"Base image invalid: {base_path} - {result.message}")
                                    all_checks_passed = False
                        
                        if not base_image_found:
                            check_progress.log_error("No valid base image found")
                            check_progress.log_info("💡 Ensure basevm.qcow2 exists and is valid")
                            all_checks_passed = False
                        
                        check_progress.complete_step("base_images")
                    else:
                        # No traditional KVM guests, skip base image check
                        if kvm_auto_guests:
                            check_progress.log_success("Using kvm-auto guests (no base image required)")
                        else:
                            check_progress.log_warning("No KVM guests found in configuration")
                    
                    # Step 3: Check cloud-init.iso availability
                    check_progress.start_step("cloud_init", "Checking cloud-init requirements...")
                    cloud_init_paths = [
                        "/home/ubuntu/cyris/docs/images/cloud-init.iso",
                        "/home/ubuntu/cyris/images/cloud-init.iso"
                    ]
                    
                    cloud_init_found = any(Path(p).exists() for p in cloud_init_paths)
                    if cloud_init_found:
                        check_progress.log_success("cloud-init.iso found")
                    else:
                        check_progress.log_warning("cloud-init.iso not found")
                        check_progress.log_info("💡 VMs may fail to initialize properly")
                        help_info = get_diagnostic_pattern_help("missing_cloud_init")
                        check_progress.log_info(f"💡 {help_info['quick_fix']}")
                        # Note: This is a warning, not a failure for kvm-auto
                    check_progress.complete_step("cloud_init")
                    
                    # Step 4: Check libvirt connectivity
                    check_progress.start_step("libvirt", "Testing libvirt connectivity...")
                    try:
                        import subprocess
                        result = subprocess.run(['virsh', 'version'], capture_output=True, timeout=5)
                        if result.returncode == 0:
                            check_progress.log_success("libvirt connectivity confirmed")
                        else:
                            check_progress.log_error("libvirt not accessible")
                            all_checks_passed = False
                    except Exception as e:
                        check_progress.log_error(f"libvirt check failed: {str(e)}")
                        all_checks_passed = False
                    check_progress.complete_step("libvirt")
                    
                    # Step 5: Check network configuration
                    check_progress.start_step("network", "Checking network configuration...")
                    try:
                        import subprocess
                        result = subprocess.run(['virsh', 'net-list', '--active'], capture_output=True, timeout=5)
                        if result.returncode == 0 and b'default' in result.stdout:
                            check_progress.log_success("Default network available")
                        else:
                            check_progress.log_warning("Default network may not be active")
                            # This is a warning, not necessarily a failure
                    except Exception as e:
                        check_progress.log_warning(f"Network configuration check failed: {str(e)}")
                    check_progress.complete_step("network")
                    
                    # Step 6: Check for kvm-auto requirements
                    check_progress.start_step("kvm_auto", "Checking kvm-auto requirements...")
                    kvm_auto_check_passed = self._check_kvm_auto_requirements(description_file)
                    if kvm_auto_check_passed:
                        check_progress.log_success("kvm-auto requirements satisfied")
                    else:
                        check_progress.log_error("kvm-auto requirements not met")
                        all_checks_passed = False
                    check_progress.complete_step("kvm_auto")
                    
                except Exception as e:
                    check_progress.log_error(f"Pre-check failed: {str(e)}")
                    all_checks_passed = False
        
        if all_checks_passed:
            self.console.print("  🎉 All pre-checks passed!")
        
        return all_checks_passed
    
    def _check_kvm_auto_requirements(self, description_file: Path) -> bool:
        """Check kvm-auto specific requirements"""
        try:
            # Parse YAML to check for kvm-auto guests
            from cyris.config.parser import CyRISConfigParser
            from cyris.domain.entities.guest import BaseVMType
            from cyris.infrastructure.image_builder import LocalImageBuilder
            
            parser = CyRISConfigParser()
            config = parser.parse_file(description_file)
            
            kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
            
            if not kvm_auto_guests:
                # No kvm-auto guests, skip checks
                return True
            
            self.console.print(f"  🔧 Checking kvm-auto requirements for {len(kvm_auto_guests)} guests...")
            
            image_builder = LocalImageBuilder()
            deps = image_builder.check_local_dependencies()
            
            all_passed = True
            
            # Check virt-builder availability
            if not deps.get('virt-builder', False):
                self.console.print("  ❌ virt-builder not available (required for kvm-auto)")
                self.console.print("     💡 Install with: sudo apt install libguestfs-tools")
                all_passed = False
            else:
                self.console.print("  ✅ virt-builder available")
            
            # Check virt-customize availability
            if not deps.get('virt-customize', False):
                self.console.print("  ❌ virt-customize not available (required for kvm-auto tasks)")
                self.console.print("     💡 Install with: sudo apt install libguestfs-tools")
                all_passed = False
            else:
                self.console.print("  ✅ virt-customize available")
            
            # Check virt-install availability
            if not deps.get('virt-install', False):
                self.console.print("  ❌ virt-install not available (required for kvm-auto)")
                self.console.print("     💡 Install with: sudo apt install virtinst")
                all_passed = False
            else:
                self.console.print("  ✅ virt-install available")
            
            # Validate image names against available images
            if deps.get('virt-builder', False):
                available_images = image_builder.get_available_images()
                
                for guest in kvm_auto_guests:
                    if guest.image_name not in available_images:
                        self.console.print(f"  ❌ Image '{guest.image_name}' not available")
                        self.console.print(f"     💡 Available images: {', '.join(available_images[:5])}...")
                        self.console.print("     💡 Run: virt-builder --list for full list")
                        all_passed = False
                    else:
                        self.console.print(f"  ✅ Image '{guest.image_name}' available")
            
            # Show kvm-auto configuration example if there are issues
            if not all_passed:
                self.console.print("\n  📋 Example kvm-auto configuration:")
                self.console.print("     [cyan]guest_settings:[/cyan]")
                self.console.print("     [cyan]  - id: ubuntu-desktop[/cyan]")
                self.console.print("     [cyan]    basevm_type: kvm-auto[/cyan]")
                self.console.print("     [cyan]    image_name: ubuntu-20.04[/cyan]")
                self.console.print("     [cyan]    vcpus: 2[/cyan]")
                self.console.print("     [cyan]    memory: 2048[/cyan]")
                self.console.print("     [cyan]    disk_size: 20G[/cyan]")
                self.console.print("     [cyan]    tasks:[/cyan]")
                self.console.print("     [cyan]    - add_account:[/cyan]")
                self.console.print("     [cyan]      - account: trainee[/cyan]")
                self.console.print("     [cyan]        passwd: training123[/cyan]")
            
            return all_passed
            
        except Exception as e:
            self.console.print(f"  ❌ kvm-auto validation failed: {e}")
            return False
    
    def _run_post_creation_validation(self, range_id: str, orchestrator) -> None:
        """Validate VM health after creation (legacy method)"""
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

    def _run_post_creation_validation_with_progress(self, range_id: str, orchestrator, progress_manager) -> bool:
        """Validate VM health after creation with Rich progress tracking"""
        
        try:
            # Wait for VMs to initialize
            progress_manager.log_info("Waiting for VMs to initialize...")
            import time
            time.sleep(5)
            
            # Get range resources
            resources = orchestrator.get_range_resources(range_id)
            if not resources or not resources.get('guests'):
                progress_manager.log_error("No VMs found in created range")
                return False
            
            vm_count = len(resources['guests'])
            progress_manager.log_info(f"Validating {vm_count} VMs...")
            
            vm_issues_found = False
            diagnostics = VMDiagnostics()
            
            for i, vm_name in enumerate(resources['guests']):
                progress_manager.update_step("validate", completed=int((i/vm_count) * 100))
                
                try:
                    progress_manager.log_info(f"Checking VM: {vm_name}")
                    
                    # Quick health check
                    health_results = diagnostics.check_cloud_init_config(vm_name)
                    health_results.extend(diagnostics.check_vm_image_health(vm_name))
                    
                    # Check for critical issues
                    critical_issues = [r for r in health_results if r.level.value in ['error', 'critical']]
                    
                    if critical_issues:
                        progress_manager.log_error(f"{vm_name}: {len(critical_issues)} issue(s) detected")
                        for issue in critical_issues[:2]:  # Show top 2 issues
                            progress_manager.log_warning(f"  • {issue.message}")
                            if issue.suggestion:
                                progress_manager.log_info(f"    💡 {issue.suggestion}")
                        vm_issues_found = True
                    else:
                        progress_manager.log_success(f"{vm_name}: Initial validation passed")
                        
                except Exception as e:
                    progress_manager.log_error(f"{vm_name}: Validation check failed - {str(e)}")
                    vm_issues_found = True
            
            if vm_issues_found:
                progress_manager.log_info(f"💡 Tip: Use 'cyris status {range_id} --verbose' for detailed diagnostics")
                return False
            else:
                progress_manager.log_success("🎉 All VMs appear healthy!")
                return True
                
        except Exception as e:
            progress_manager.log_error(f"Post-validation failed: {str(e)}")
            return False
    
    def _check_kvm_auto_requirements_with_progress(self, description_file: Path, progress_manager) -> bool:
        """Check kvm-auto specific requirements with progress tracking"""
        try:
            # Parse YAML to check for kvm-auto guests
            from cyris.config.parser import CyRISConfigParser
            from cyris.domain.entities.guest import BaseVMType
            from cyris.infrastructure.image_builder import LocalImageBuilder
            
            parser = CyRISConfigParser()
            config = parser.parse_file(description_file)
            
            kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
            
            if not kvm_auto_guests:
                # No kvm-auto guests, skip checks
                return True
            
            progress_manager.log_info(f"Checking kvm-auto requirements for {len(kvm_auto_guests)} guests...")
            
            image_builder = LocalImageBuilder()
            deps = image_builder.check_local_dependencies()
            
            all_passed = True
            
            # Check virt-builder availability
            if not deps.get('virt-builder', False):
                progress_manager.log_error("virt-builder not available (required for kvm-auto)")
                progress_manager.log_info("Install with: sudo apt install libguestfs-tools")
                all_passed = False
            else:
                progress_manager.log_success("virt-builder available")
            
            # Check virt-customize availability
            if not deps.get('virt-customize', False):
                progress_manager.log_error("virt-customize not available (required for kvm-auto tasks)")
                progress_manager.log_info("Install with: sudo apt install libguestfs-tools")
                all_passed = False
            else:
                progress_manager.log_success("virt-customize available")
            
            # Check virt-install availability
            if not deps.get('virt-install', False):
                progress_manager.log_error("virt-install not available (required for kvm-auto)")
                progress_manager.log_info("Install with: sudo apt install virtinst")
                all_passed = False
            else:
                progress_manager.log_success("virt-install available")
            
            # Validate image names against available images
            if deps.get('virt-builder', False):
                available_images = image_builder.get_available_images()
                
                for guest in kvm_auto_guests:
                    if guest.image_name not in available_images:
                        progress_manager.log_error(f"Image '{guest.image_name}' not available")
                        progress_manager.log_info(f"Available images: {', '.join(available_images[:5])}...")
                        progress_manager.log_info("Run: virt-builder --list for full list")
                        all_passed = False
                    else:
                        progress_manager.log_success(f"Image '{guest.image_name}' available")
            
            # Show kvm-auto configuration example if there are issues
            if not all_passed:
                progress_manager.log_info("Example kvm-auto configuration:")
                progress_manager.log_info("  guest_settings:")
                progress_manager.log_info("    - id: ubuntu-desktop")
                progress_manager.log_info("      basevm_type: kvm-auto")
                progress_manager.log_info("      image_name: ubuntu-20.04")
                progress_manager.log_info("      vcpus: 2")
                progress_manager.log_info("      memory: 2048")
                progress_manager.log_info("      disk_size: 20G")
            
            return all_passed
            
        except Exception as e:
            progress_manager.log_error(f"kvm-auto validation failed: {e}")
            return False