#!/usr/bin/env python3
"""
CyRIS Modern Command Line Interface
Supports modern commands while maintaining backward compatibility
"""
import sys
import click
from pathlib import Path
from typing import Optional
import logging
import locale
import os

from ..config.parser import parse_modern_config, ConfigurationError
from ..config.settings import CyRISSettings


# Setup logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


# Smart emoji/UTF-8 detection
def _detect_terminal_capabilities():
    """Detect terminal capabilities for emoji and color support"""
    # Check encoding support
    enc = (sys.stdout.encoding or locale.getpreferredencoding(False) or '').upper()
    utf8_support = 'UTF-8' in enc or 'UTF8' in enc
    
    # Check environment variables
    no_color = os.environ.get('NO_COLOR', '').strip().lower() in ('1', 'true', 'yes')
    term = os.environ.get('TERM', '').lower()
    
    # Basic terminal detection
    supports_color = not no_color and term not in ('dumb', 'unknown', '')
    
    # Conservative emoji support - disabled by default to avoid terminal corruption
    # Only enable if explicitly requested via environment variable
    enable_emoji_override = os.environ.get('CYRIS_ENABLE_EMOJI', '').strip().lower()
    
    if enable_emoji_override in ('1', 'true', 'yes'):
        # User explicitly wants emoji - enable if basic requirements met
        supports_emoji = utf8_support and supports_color
    else:
        # Default: very conservative, disable emoji to avoid terminal issues
        supports_emoji = False
    
    return {
        'utf8_support': utf8_support,
        'supports_color': supports_color,
        'supports_emoji': supports_emoji,
        'encoding': enc,
        'term': term
    }


# Global terminal capabilities
TERMINAL_CAPS = _detect_terminal_capabilities()

def get_status_indicator(status: str, use_emoji: bool = None) -> str:
    """Get appropriate status indicator based on terminal capabilities"""
    if use_emoji is None:
        use_emoji = TERMINAL_CAPS['supports_emoji']
    
    if use_emoji:
        indicators = {
            'active': '🟢',
            'creating': '🟡', 
            'error': '🔴',
            'ok': '✅',
            'fail': '❌',
            'warning': '⚠️',
            'info': '💡'
        }
    else:
        indicators = {
            'active': '[ACTIVE]',
            'creating': '[CREATING]',
            'error': '[ERROR]', 
            'ok': '[OK]',
            'fail': '[ERROR]',
            'warning': '[WARN]',
            'info': '[INFO]'
        }
    
    return indicators.get(status.lower(), f'[{status.upper()}]')


def get_config(ctx) -> 'CyRISSettings':
    """Get configuration from context with fallback"""
    if ctx.obj is None:
        ctx.obj = {'config': CyRISSettings()}
    elif 'config' not in ctx.obj:
        ctx.obj['config'] = CyRISSettings()
    
    return ctx.obj['config']




@click.group()
@click.option('--config', '-c', 
              type=click.Path(exists=True),
              help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--version', is_flag=True, help='Show version information')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool, version: bool):
    """
    CyRIS - Modern Cyber Security Training Environment Deployment Tool
    
    Use modern command line interface to manage cyber range creation, deployment and management.
    """
    # Handle version option
    if version:
        click.echo("CyRIS v1.4.0 - Cyber Range Instantiation System")
        ctx.exit()
    
    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize context
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # Load configuration
    if config:
        try:
            config_path = Path(config)
            settings = parse_modern_config(config_path)
            ctx.obj['config'] = settings
            if verbose:
                click.echo(f"Configuration loaded: {config}")
        except ConfigurationError as e:
            click.echo(f"Configuration error: {e}", err=True)
            sys.exit(1)
    else:
        # Try loading configuration from default locations
        default_configs = [
            Path.cwd() / 'config.yml',
            Path.cwd() / 'config.yaml', 
            Path.cwd() / 'CONFIG'
        ]
        
        settings = None
        for config_path in default_configs:
            if config_path.exists():
                try:
                    settings = parse_modern_config(config_path)
                    if verbose:
                        click.echo(f"Auto-loaded configuration: {config_path}")
                    break
                except ConfigurationError:
                    continue
        
        if settings is None:
            # Use default configuration
            settings = CyRISSettings()
            if verbose:
                click.echo("Using default configuration")
        
        ctx.obj['config'] = settings


@cli.command()
@click.argument('description_file', type=click.Path(exists=True, path_type=Path))
@click.option('--range-id', type=int, help='Specify cyber range ID')
@click.option('--dry-run', is_flag=True, help='Dry run mode, do not actually create')
@click.option('--network-mode', 
              type=click.Choice(['user', 'bridge'], case_sensitive=False),
              default='user',
              help='Network mode: user (isolated) or bridge (SSH accessible)')
@click.option('--enable-ssh', is_flag=True, help='Enable SSH access (requires bridge networking)')
@click.pass_context
def create(ctx, description_file: Path, range_id: Optional[int], dry_run: bool, network_mode: str, enable_ssh: bool):
    """
    Create a new cyber range
    
    DESCRIPTION_FILE: YAML format cyber range description file
    """
    config: CyRISSettings = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    click.echo(f"Creating cyber range: {description_file}")
    
    if verbose:
        click.echo(f"Configuration: {config}")
        click.echo(f"Range ID: {range_id or 'auto-assigned'}")
    
    if dry_run:
        click.echo("Dry run mode - will not actually create cyber range")
        try:
            # Still create orchestrator and validate YAML in dry-run mode
            from ..services.orchestrator import RangeOrchestrator
            from ..infrastructure.providers.kvm_provider import KVMProvider
            
            # Configure network settings
            libvirt_uri = 'qemu:///system' if network_mode == 'bridge' else 'qemu:///session'
            
            kvm_settings = {
                'connection_uri': libvirt_uri,
                'libvirt_uri': libvirt_uri,
                'base_path': str(config.cyber_range_dir),
                'network_mode': network_mode,
                'enable_ssh': enable_ssh
            }
            provider = KVMProvider(kvm_settings)
            orchestrator = RangeOrchestrator(config, provider)
            
            result = orchestrator.create_range_from_yaml(
                description_file=description_file,
                range_id=range_id,
                dry_run=True
            )
            
            if result:
                click.echo(f"[OK] Validation successful. Would create range: {result}")
            else:
                click.echo("[ERROR] Validation failed")
                sys.exit(1)
        except Exception as e:
            click.echo(f"[ERROR] Validation error: {e}", err=True)
            if verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        return
    
    # Implement actual cyber range creation using service layer
    try:
        from ..services.orchestrator import RangeOrchestrator
        from ..infrastructure.providers.kvm_provider import KVMProvider
        
        # Create infrastructure provider (default to KVM)
        # Configure network settings
        libvirt_uri = 'qemu:///system' if network_mode == 'bridge' else 'qemu:///session'
        
        kvm_settings = {
            'connection_uri': libvirt_uri,
            'libvirt_uri': libvirt_uri,
            'base_path': str(config.cyber_range_dir),
            'network_mode': network_mode,
            'enable_ssh': enable_ssh
        }
        provider = KVMProvider(kvm_settings)
        
        # Create orchestrator
        orchestrator = RangeOrchestrator(config, provider)
        
        # Create range
        click.echo("Initializing cyber range creation...")
        result = orchestrator.create_range_from_yaml(
            description_file=description_file,
            range_id=range_id,
            dry_run=dry_run
        )
        
        if result:
            click.echo(f"[OK] Cyber range created successfully: {result}")
        else:
            click.echo("[ERROR] Cyber range creation failed")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"[ERROR] Error creating cyber range: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--range-id', type=int, help='Cyber range ID')
@click.option('--all', 'list_all', is_flag=True, help='Show all cyber ranges')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information including VM IPs')
@click.pass_context
def list(ctx, range_id: Optional[int], list_all: bool, verbose: bool):
    """List cyber ranges"""
    config: CyRISSettings = get_config(ctx)
    
    try:
        # Flush stdout to ensure proper ordering with stderr logging
        sys.stdout.flush()
        
        from ..services.orchestrator import RangeOrchestrator
        from ..infrastructure.providers.kvm_provider import KVMProvider
        
        # Create orchestrator to check ranges
        kvm_settings = {'connection_uri': 'qemu:///system', 'base_path': str(config.cyber_range_dir)}
        provider = KVMProvider(kvm_settings)
        orchestrator = RangeOrchestrator(config, provider)
        
        if range_id:
            # Show specific range details
            click.echo(f"Cyber range {range_id} details:")
            range_metadata = orchestrator.get_range(range_id)
            if range_metadata:
                click.echo(f"  Name: {range_metadata.name}")
                click.echo(f"  Status: {range_metadata.status.value}")
                click.echo(f"  Created: {range_metadata.created_at}")
                click.echo(f"  Description: {range_metadata.description}")
                if range_metadata.tags:
                    click.echo(f"  Tags: {range_metadata.tags}")
            else:
                click.echo(f"  Range {range_id} not found in orchestrator")
        else:
            # List ranges
            ranges = orchestrator.list_ranges()
            
            if not ranges:
                click.echo("No cyber ranges found in orchestrator")
                
                # Fallback: Check filesystem for range directories  
                ranges_dir = config.cyber_range_dir
                if ranges_dir.exists():
                    range_dirs = [d for d in ranges_dir.iterdir() if d.is_dir()]
                    if range_dirs:
                        click.echo(f"Found {len(range_dirs)} range directories on filesystem:")
                        for range_dir in sorted(range_dirs):
                            click.echo(f"  {range_dir.name} (filesystem only)")
                else:
                    click.echo(f"Cyber range directory does not exist: {ranges_dir}")
                
                # Check for running VMs that might be orphaned
                _check_running_vms(provider)
                return
            
            # Display orchestrated ranges
            click.echo(f"Cyber ranges ({'all' if list_all else 'active only'}):")
            
            displayed_count = 0
            for range_meta in sorted(ranges, key=lambda r: r.created_at):
                if not list_all and range_meta.status.value not in ['active', 'creating']:
                    continue
                    
                displayed_count += 1
                
                # Use smart status indicators with emoji fallback
                if range_meta.status.value == "active":
                    status_indicator = get_status_indicator('active')
                elif range_meta.status.value == "creating":
                    status_indicator = get_status_indicator('creating')
                else:
                    status_indicator = get_status_indicator('error')
                
                click.echo(f"  {status_indicator} {range_meta.range_id}: {range_meta.name}")
                click.echo(f"     Status: {range_meta.status.value}")
                click.echo(f"     Created: {range_meta.created_at.strftime('%Y-%m-%d %H:%M')}")
                if range_meta.description:
                    click.echo(f"     Description: {range_meta.description}")
                
                # Show VM status information if verbose and range is active
                if verbose and range_meta.status.value in ['active', 'creating']:
                    resources = orchestrator.get_range_resources(range_meta.range_id)
                    if resources and resources.get('guests'):
                        # Get libvirt URI from range metadata
                        libvirt_uri = "qemu:///system"
                        if range_meta.provider_config:
                            libvirt_uri = range_meta.provider_config.get('libvirt_uri', libvirt_uri)
                        
                        try:
                            from ..tools.vm_ip_manager import VMIPManager
                            ip_manager = VMIPManager(libvirt_uri=libvirt_uri)
                            
                            vm_statuses = []
                            has_issues = False
                            
                            for guest in resources['guests']:
                                try:
                                    health_info = ip_manager.get_vm_health_info(guest)
                                    
                                    # Use smart status indicators with emoji fallback
                                    status_icon = get_status_indicator('ok') if health_info.is_healthy else get_status_indicator('fail')
                                    compact_status = health_info.get_compact_status()
                                    
                                    vm_status = f"{status_icon} {guest}: {compact_status}"
                                    vm_statuses.append(vm_status)
                                    
                                    # Track if there are any issues
                                    if health_info.error_details or not health_info.is_healthy:
                                        has_issues = True
                                        
                                except Exception:
                                    vm_statuses.append(f"[FAIL] {guest}: check failed")
                                    has_issues = True
                            
                            if vm_statuses:
                                click.echo(f"     VMs: {' | '.join(vm_statuses)}")
                                
                                # If there are issues, show a hint
                                if has_issues:
                                    click.echo(f"     HINT: Issues detected - use 'cyris status {range_meta.range_id} --verbose' for details")
                            
                            ip_manager.close()
                            
                        except ImportError:
                            click.echo(f"     WARNING:  VM status checking not available")
                        except Exception:
                            pass  # Silently skip health check errors in list mode
            
            if displayed_count == 0:
                click.echo("  No ranges match the filter criteria")
        
        # Ensure all output is flushed before any remaining logs
        sys.stdout.flush()
        sys.stderr.flush()
                
    except Exception as e:
        click.echo(f"Error listing cyber ranges: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('range_id')  # Accept both string and numeric range IDs
@click.option('--force', '-f', is_flag=True, help='Force deletion without confirmation')
@click.option('--rm', is_flag=True, help='Remove all records after destroying (like docker run --rm)')
@click.pass_context
def destroy(ctx, range_id: str, force: bool, rm: bool):
    """
    Destroy the specified cyber range (stops VMs, cleans up resources)
    
    RANGE_ID: ID of the cyber range to destroy
    
    By default, this stops all VMs and cleans up resources but keeps metadata
    for audit/history purposes. The range status becomes "destroyed".
    
    Options:
      --force  Skip confirmation prompt
      --rm     Also remove all records after destroying (like docker run --rm)
    
    Examples:
      cyris destroy 123           # Destroy range 123, keep records
      cyris destroy 123 --rm      # Destroy and remove all traces
      cyris destroy 123 --force   # Destroy without confirmation
    
    See also: cyris rm - to remove destroyed ranges later
    """
    config: CyRISSettings = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    if not force:
        if not click.confirm(f'Are you sure you want to destroy cyber range {range_id}?'):
            click.echo('Operation cancelled')
            return
    
    click.echo(f"Destroying cyber range: {range_id}")
    
    try:
        from ..services.orchestrator import RangeOrchestrator
        from ..infrastructure.providers.kvm_provider import KVMProvider
        
        # First, create a basic orchestrator to check range metadata
        basic_kvm_settings = {'connection_uri': 'qemu:///session', 'base_path': str(config.cyber_range_dir)}
        basic_provider = KVMProvider(basic_kvm_settings)
        basic_orchestrator = RangeOrchestrator(config, basic_provider)
        
        # Check if range exists and get its original connection info
        range_metadata = basic_orchestrator.get_range(range_id)
        if not range_metadata:
            click.echo(f"[ERROR] Cyber range {range_id} not found")
            
            # Check filesystem for legacy ranges
            range_dir = config.cyber_range_dir / range_id
            if range_dir.exists():
                click.echo(f"WARNING:  Found range directory on filesystem: {range_dir}")
                click.echo(f"   Use legacy cleanup: main/range_cleanup.sh {range_id} CONFIG")
            
            sys.exit(1)
        
        # Determine the correct libvirt connection for this range
        libvirt_uri = 'qemu:///system'  # Default
        if range_metadata.provider_config and 'libvirt_uri' in range_metadata.provider_config:
            libvirt_uri = range_metadata.provider_config['libvirt_uri']
            if verbose:
                click.echo(f"Using detected libvirt URI: {libvirt_uri}")
        else:
            if verbose:
                click.echo(f"No provider config found, using default: {libvirt_uri}")
        
        # Create orchestrator with the correct connection
        kvm_settings = {'connection_uri': libvirt_uri, 'base_path': str(config.cyber_range_dir)}
        provider = KVMProvider(kvm_settings)
        orchestrator = RangeOrchestrator(config, provider)
        
        # Destroy the range
        success = orchestrator.destroy_range(range_id)
        
        if success:
            click.echo(f"[OK] Cyber range {range_id} destroyed successfully")
            
            # If --rm flag is set, also remove all records
            if rm:
                click.echo(f"🗑️  Removing all records for cyber range {range_id}...")
                remove_success = orchestrator.remove_range(range_id, force=force)
                if remove_success:
                    click.echo(f"[OK] All records for cyber range {range_id} removed completely")
                else:
                    click.echo(f"WARNING:  Failed to remove records for cyber range {range_id}")
                    click.echo(f"   You can manually run: cyris rm {range_id}")
        else:
            click.echo(f"[ERROR] Failed to destroy cyber range {range_id}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"[ERROR] Error destroying cyber range: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('range_id')  # Accept both string and numeric range IDs
@click.option('--force', '-f', is_flag=True, help='Force removal even if range is not destroyed')
@click.pass_context
def rm(ctx, range_id: str, force: bool):
    """
    Remove a cyber range completely from the system (including all files and records)
    
    RANGE_ID: ID of the cyber range to remove
    
    By default, only destroyed ranges can be removed for safety.
    Use --force to remove active ranges (will destroy them first).
    
    This is equivalent to Docker's "rm" command - completely removes all traces:
    - Metadata and tracking records
    - Disk image files (*.qcow2)
    - Range directories and logs
    - Associated configuration files
    
    Examples:
      cyris rm 123              # Remove destroyed range 123
      cyris rm 456 --force      # Force remove active range 456
      cyris destroy 789 --rm    # Destroy and remove in one step
    """
    config: CyRISSettings = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    # Safety confirmation
    range_desc = f"cyber range {range_id}"
    if force:
        range_desc += " (FORCE - will destroy if active)"
    
    if not click.confirm(f'Are you sure you want to completely remove {range_desc}?\nThis will delete all files, images, and records permanently.'):
        click.echo('Operation cancelled')
        return
    
    click.echo(f"Removing cyber range: {range_id}")
    
    try:
        from ..services.orchestrator import RangeOrchestrator
        from ..infrastructure.providers.kvm_provider import KVMProvider
        
        # Create orchestrator
        kvm_settings = {'connection_uri': 'qemu:///system', 'base_path': str(config.cyber_range_dir)}
        provider = KVMProvider(kvm_settings)
        orchestrator = RangeOrchestrator(config, provider)
        
        # Check if range exists
        range_metadata = orchestrator.get_range(range_id)
        if not range_metadata:
            click.echo(f"[ERROR] Cyber range {range_id} not found")
            
            # Check filesystem for legacy ranges
            range_dir = config.cyber_range_dir / range_id
            if range_dir.exists():
                click.echo(f"WARNING:  Found range directory on filesystem: {range_dir}")
                if click.confirm("Remove filesystem directory anyway?"):
                    import shutil
                    shutil.rmtree(range_dir)
                    click.echo(f"[OK] Removed directory {range_dir}")
            
            sys.exit(1)
        
        # Show range info before removal
        click.echo(f"Range: {range_metadata.name}")
        click.echo(f"Status: {range_metadata.status.value}")
        click.echo(f"Created: {range_metadata.created_at}")
        
        # Remove the range (with force flag)
        success = orchestrator.remove_range(range_id, force=force)
        
        if success:
            click.echo(f"[OK] Cyber range {range_id} removed completely")
            click.echo("   All files, images, and records have been deleted")
        else:
            click.echo(f"[ERROR] Failed to remove cyber range {range_id}")
            if not force and range_metadata.status.value != 'destroyed':
                click.echo(f"   Range status is '{range_metadata.status.value}' - use --force to remove active ranges")
                click.echo(f"   Or destroy first: cyris destroy {range_id}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"[ERROR] Error removing cyber range: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('range_id')  # Accept both string and numeric range IDs
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information including VM IPs')
@click.pass_context
def status(ctx, range_id: str, verbose: bool):
    """
    Display cyber range status
    
    RANGE_ID: Cyber range ID
    """
    config: CyRISSettings = get_config(ctx)
    
    click.echo(f"Cyber range {range_id} status:")
    
    try:
        from ..services.orchestrator import RangeOrchestrator
        from ..infrastructure.providers.kvm_provider import KVMProvider
        
        # Create orchestrator
        kvm_settings = {'connection_uri': 'qemu:///system', 'base_path': str(config.cyber_range_dir)}
        provider = KVMProvider(kvm_settings)
        orchestrator = RangeOrchestrator(config, provider)
        
        # Check orchestrator first
        range_metadata = orchestrator.get_range(range_id)
        
        if range_metadata:
            # Show orchestrator information with smart status indicators
            if range_metadata.status.value == "active":
                status_icon = get_status_indicator('active')
            elif range_metadata.status.value == "creating":
                status_icon = get_status_indicator('creating')
            else:
                status_icon = get_status_indicator('error')
            click.echo(f"  {status_icon} Status: {range_metadata.status.value}")
            click.echo(f"  Name: {range_metadata.name}")
            click.echo(f"  Description: {range_metadata.description}")
            click.echo(f"  Created: {range_metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"  Last Modified: {range_metadata.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if range_metadata.owner:
                click.echo(f"  Owner: {range_metadata.owner}")
            
            if range_metadata.tags:
                click.echo(f"  Tags: {range_metadata.tags}")
            
            # Show resource information
            resources = orchestrator.get_range_resources(range_id)
            if resources:
                click.echo(f"  Resources:")
                if resources.get('hosts'):
                    click.echo(f"    Hosts: {len(resources['hosts'])}")
                if resources.get('guests'):
                    click.echo(f"    Guests: {len(resources['guests'])}")
                    
                    # Show VM health information
                    if resources.get('guests') and verbose:
                        click.echo(f"  INFO: Virtual Machine Health Status:")
                        
                        # Get libvirt URI from range metadata
                        libvirt_uri = "qemu:///system"
                        if range_metadata.provider_config:
                            libvirt_uri = range_metadata.provider_config.get('libvirt_uri', libvirt_uri)
                        
                        try:
                            from ..tools.vm_ip_manager import VMIPManager
                            ip_manager = VMIPManager(libvirt_uri=libvirt_uri)
                            
                            for guest in resources['guests']:
                                try:
                                    health_info = ip_manager.get_vm_health_info(guest)
                                    
                                    # Smart status indicators with emoji fallback
                                    status_icon = get_status_indicator('ok') if health_info.is_healthy else get_status_indicator('error')
                                    
                                    click.echo(f"    {status_icon} {guest}")
                                    click.echo(f"       libvirt: {health_info.libvirt_status} | healthy: {health_info.is_healthy}")
                                    
                                    if health_info.ip_addresses:
                                        click.echo(f"       IP: IP: {', '.join(health_info.ip_addresses)}")
                                        if health_info.network_reachable:
                                            click.echo(f"       NET: Network: reachable")
                                        else:
                                            click.echo(f"       NET: Network: not reachable")
                                    else:
                                        click.echo(f"       IP: IP: not assigned")
                                    
                                    if health_info.uptime:
                                        click.echo(f"       TIME:  Uptime: {health_info.uptime}")
                                    
                                    if health_info.disk_path:
                                        click.echo(f"       DISK: Disk: {health_info.disk_path}")
                                    
                                    # Show all error details directly
                                    if health_info.error_details:
                                        click.echo(f"       INFO: Error Details:")
                                        for i, error in enumerate(health_info.error_details, 1):
                                            # For very long errors, wrap them nicely
                                            if len(error) > 80:
                                                click.echo(f"         {i}. {error[:77]}...")
                                                click.echo(f"            {error[77:]}")
                                            else:
                                                click.echo(f"         {i}. {error}")
                                    
                                    click.echo()  # Empty line between VMs
                                    
                                except Exception as e:
                                    click.echo(f"    [ERROR] {guest}: Health check failed - {e}")
                            
                            ip_manager.close()
                            
                        except ImportError:
                            click.echo(f"    WARNING:  VM health checking not available")
                        except Exception as e:
                            click.echo(f"    [ERROR] Health check error: {e}")
                    
                    elif resources.get('guests'):
                        click.echo(f"    💡 Use --verbose to see detailed VM health status")
        
        else:
            click.echo(f"  [ERROR] Range not found in orchestrator")
        
        # Check filesystem regardless
        range_dir = config.cyber_range_dir / range_id
        
        if range_dir.exists():
            click.echo(f"  DIR: Directory: {range_dir}")
            
            # Show directory contents if verbose
            if verbose:
                try:
                    contents = []
                    for item in range_dir.iterdir():
                        contents.append(item)
                    
                    click.echo(f"  Directory contents ({len(contents)} items):")
                    for item in sorted(contents):
                        item_type = "DIR:" if item.is_dir() else "FILE:"
                        click.echo(f"    {item_type} {item.name}")
                        
                except Exception as e:
                    click.echo(f"    Could not list directory contents: {e}")
        else:
            if not range_metadata:
                click.echo(f"  [ERROR] Range {range_id} not found (no orchestrator record, no filesystem directory)")
                sys.exit(1)
            else:
                click.echo(f"  WARNING:  Range exists in orchestrator but no filesystem directory found")
                
    except Exception as e:
        click.echo(f"[ERROR] Error checking range status: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    config: CyRISSettings = get_config(ctx)
    
    click.echo("Current configuration:")
    click.echo(f"  CyRIS path: {config.cyris_path}")
    click.echo(f"  Cyber range directory: {config.cyber_range_dir}")
    click.echo(f"  Gateway mode: {'enabled' if config.gw_mode else 'disabled'}")
    
    if config.gw_account:
        click.echo(f"  Gateway account: {config.gw_account}")
    if config.gw_mgmt_addr:
        click.echo(f"  Gateway management address: {config.gw_mgmt_addr}")
    if config.user_email:
        click.echo(f"  User email: {config.user_email}")


@cli.command()
@click.option('--output', '-o', type=click.Path(path_type=Path), 
              default='config.yml', help='Output configuration file path')
@click.pass_context
def config_init(ctx, output: Path):
    """Initialize default configuration file"""
    if output.exists():
        if not click.confirm(f'Configuration file {output} already exists. Overwrite?'):
            click.echo('Operation cancelled')
            return
    
    # Create default configuration
    from ..config.parser import create_default_config
    
    try:
        settings = create_default_config(output)
        click.echo(f"[OK] Default configuration file created: {output}")
        click.echo("Please edit the configuration file to suit your environment")
    except Exception as e:
        click.echo(f"[ERROR] Failed to create configuration file: {e}", err=True)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate environment configuration and dependencies"""
    click.echo("Validating CyRIS environment...")
    
    config: CyRISSettings = get_config(ctx)
    errors = 0
    
    # Check paths
    if not config.cyris_path.exists():
        click.echo(f"[ERROR] CyRIS path does not exist: {config.cyris_path}")
        errors += 1
    else:
        click.echo(f"[OK] CyRIS path: {config.cyris_path}")
    
    if not config.cyber_range_dir.exists():
        click.echo(f"[ERROR] Cyber range directory does not exist: {config.cyber_range_dir}")
        errors += 1
    else:
        click.echo(f"[OK] Cyber range directory: {config.cyber_range_dir}")
    
    # Check legacy scripts
    legacy_script = config.cyris_path / 'main' / 'cyris.py'
    if legacy_script.exists():
        click.echo(f"[OK] Legacy script available: {legacy_script}")
    else:
        click.echo(f"WARNING:  Legacy script not available: {legacy_script}")
    
    # Check example files
    examples_dir = config.cyris_path / 'examples'
    if examples_dir.exists():
        try:
            import os
            example_files = [f for f in os.listdir(examples_dir) if f.endswith('.yml')]
            click.echo(f"[OK] Example files: {len(example_files)} found")
        except Exception as e:
            click.echo(f"WARNING:  Error checking example files: {e}")
    else:
        click.echo(f"WARNING:  Examples directory does not exist: {examples_dir}")
    
    if errors == 0:
        click.echo("🎉 Environment validation passed!")
    else:
        click.echo(f"[ERROR] Found {errors} issues")
        sys.exit(1)


@cli.command(name='legacy')
@click.argument('args', nargs=-1)
@click.pass_context
def legacy_run(ctx, args):
    """
    Run legacy CyRIS commands
    
    This is a compatibility command that calls the original main/cyris.py script
    """
    import subprocess
    
    config: CyRISSettings = get_config(ctx)
    legacy_script = config.cyris_path / 'main' / 'cyris.py'
    
    if not legacy_script.exists():
        click.echo(f"[ERROR] Legacy script does not exist: {legacy_script}", err=True)
        sys.exit(1)
    
    # Build command
    cmd = ['python3', str(legacy_script)] + list(args)
    
    if ctx.obj['verbose']:
        click.echo(f"Executing command: {' '.join(cmd)}")
    
    try:
        # Run legacy script
        result = subprocess.run(cmd, cwd=config.cyris_path)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"[ERROR] Execution failed: {e}", err=True)
        sys.exit(1)


def main(args=None):
    """Main entry point"""
    try:
        cli(args)
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"[ERROR] Unexpected error: {e}", err=True)
        sys.exit(1)


def _check_running_vms(provider):
    """Check for running VMs that might not be tracked by orchestrator"""
    try:
        import subprocess
        result = subprocess.run(
            ['virsh', '--connect', 'qemu:///session', 'list', '--name'],
            capture_output=True, text=True, check=True
        )
        
        running_vms = [name.strip() for name in result.stdout.split('\n') if name.strip()]
        
        if running_vms:
            cyris_vms = [vm for vm in running_vms if vm.startswith('cyris-')]
            if cyris_vms:
                click.echo(f"\nRunning KVM VMs (potentially orphaned):")
                for vm in cyris_vms:
                    click.echo(f"  [ERROR] {vm} (running but not in orchestrator)")
                click.echo(f"  Found {len(cyris_vms)} CyRIS VMs running in KVM")
                click.echo("  These VMs may be from previous sessions or failed cleanups.")
                click.echo("  Use 'virsh --connect qemu:///session destroy <vm-name>' to stop them")
            else:
                click.echo("\nNo CyRIS VMs currently running in KVM")
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        # virsh not available or not working
        pass
    except Exception as e:
        # Don't fail the whole command if VM check fails
        if click.get_current_context().obj.get('verbose', False):
            click.echo(f"Warning: Failed to check running VMs: {e}")


@cli.command(name='ssh-info')
@click.argument('range_id', type=str)
@click.pass_context
def ssh_info(ctx, range_id: str):
    """
    Get SSH connection information for a cyber range
    
    RANGE_ID: ID of the cyber range to get SSH info for
    """
    config: CyRISSettings = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    try:
        from ..services.orchestrator import RangeOrchestrator
        from ..infrastructure.providers.kvm_provider import KVMProvider
        
        # Create provider and orchestrator
        kvm_settings = {
            'connection_uri': 'qemu:///system',
            'libvirt_uri': 'qemu:///system',
            'base_path': str(config.cyber_range_dir)
        }
        provider = KVMProvider(kvm_settings)
        orchestrator = RangeOrchestrator(config, provider)
        
        # Get range information
        range_metadata = orchestrator.get_range(range_id)
        if not range_metadata:
            click.echo(f"[ERROR] Range {range_id} not found", err=True)
            sys.exit(1)
        
        # Get range resources
        resources = orchestrator.get_range_resources(range_id)
        if not resources or not resources.get('guests'):
            click.echo(f"[ERROR] No VMs found for range {range_id}", err=True)
            sys.exit(1)
        
        click.echo(f"SSH Connection Information for Range {range_id}:")
        click.echo(f"Range Name: {range_metadata.name}")
        click.echo(f"Status: {range_metadata.status.value}")
        click.echo("=" * 60)
        
        # Get libvirt URI from range metadata for IP discovery
        libvirt_uri = "qemu:///system"
        if range_metadata.provider_config:
            libvirt_uri = range_metadata.provider_config.get('libvirt_uri', libvirt_uri)
        
        # Initialize IP manager for discovering VM IPs
        ip_manager = None
        try:
            from ..tools.vm_ip_manager import VMIPManager
            ip_manager = VMIPManager(libvirt_uri=libvirt_uri)
        except ImportError:
            pass
        
        # Get SSH info for each VM
        guest_ids = resources.get('guests', [])
        for vm_id in guest_ids:
            click.echo(f"\nVM:  VM: {vm_id}")
            
            # Get comprehensive health information
            vm_ip_addresses = []
            if ip_manager:
                try:
                    health_info = ip_manager.get_vm_health_info(vm_id)
                    
                    # Smart status indicators with emoji fallback
                    status_icon = get_status_indicator('ok') if health_info.is_healthy else get_status_indicator('error')
                    
                    click.echo(f"   {status_icon} Status: {health_info.libvirt_status} → {'healthy' if health_info.is_healthy else 'unhealthy'}")
                    
                    if health_info.ip_addresses:
                        vm_ip_addresses = health_info.ip_addresses
                        click.echo(f"   IP: IP Addresses: {', '.join(vm_ip_addresses)}")
                        
                        if health_info.network_reachable:
                            click.echo(f"   NET: Network: Reachable [OK]")
                        else:
                            click.echo(f"   NET: Network: Not reachable WARNING:")
                        
                        # Show direct SSH commands only if healthy
                        if health_info.is_healthy:
                            click.echo(f"   SSH: SSH Commands:")
                            for ip in vm_ip_addresses:
                                click.echo(f"      ssh user@{ip}")
                                click.echo(f"      ssh root@{ip}  # if root access is configured")
                        else:
                            click.echo(f"   WARNING:  SSH may not be available due to VM issues")
                    else:
                        click.echo(f"   IP: IP Address: Not assigned")
                    
                    # Show uptime if available
                    if health_info.uptime:
                        click.echo(f"   TIME:  Uptime: {health_info.uptime}")
                    
                    # Show disk path if available
                    if health_info.disk_path:
                        click.echo(f"   DISK: Disk: {health_info.disk_path}")
                    
                    # Show all error details directly
                    if health_info.error_details:
                        click.echo(f"   INFO: Error Details:")
                        for i, error in enumerate(health_info.error_details, 1):
                            # For very long errors, wrap them nicely
                            if len(error) > 70:
                                click.echo(f"      {i}. {error[:67]}...")
                                click.echo(f"         {error[67:]}")
                            else:
                                click.echo(f"      {i}. {error}")
                            
                except Exception as e:
                    click.echo(f"   [ERROR] Health check failed: {e}")
            
            # Get traditional SSH info from provider
            ssh_info_data = provider.get_vm_ssh_info(vm_id)
            if ssh_info_data:
                click.echo(f"   🔗 Connection Type: {ssh_info_data['connection_type']}")
                
                if ssh_info_data['connection_type'] == 'bridge':
                    click.echo(f"   NET: Network: {ssh_info_data.get('network', 'unknown')}")
                    click.echo(f"   🔗 MAC Address: {ssh_info_data.get('mac_address', 'unknown')}")
                    click.echo(f"   🚪 SSH Port: {ssh_info_data.get('ssh_port', 22)}")
                    if ssh_info_data.get('notes'):
                        click.echo(f"   📝 Notes: {ssh_info_data['notes']}")
                    
                    # Only show manual discovery commands if IP wasn't found automatically
                    if not vm_ip_addresses and 'suggested_commands' in ssh_info_data:
                        click.echo("   📋 Manual IP discovery commands:")
                        for cmd in ssh_info_data['suggested_commands']:
                            click.echo(f"      {cmd}")
                
                elif ssh_info_data['connection_type'] == 'user_mode':
                    if ssh_info_data.get('notes'):
                        click.echo(f"   📝 Notes: {ssh_info_data['notes']}")
                    if ssh_info_data.get('alternative'):
                        click.echo(f"   🔄 Alternative: {ssh_info_data['alternative']}")
            else:
                if not vm_ip_addresses:
                    click.echo("   [ERROR] SSH information not available")
        
        if ip_manager:
            ip_manager.close()
        
        click.echo("\n💡 Tips:")
        click.echo("   • For bridge networking, VMs get DHCP IP addresses")
        click.echo("   • Use 'nmap -sP 192.168.122.0/24' to scan for active IPs")
        click.echo("   • VNC console is available on all VMs for direct access")
        
    except Exception as e:
        click.echo(f"[ERROR] Error getting SSH info: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command(name='setup-permissions')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.pass_context
def setup_permissions(ctx, dry_run: bool):
    """
    Set up libvirt permissions for CyRIS environment
    
    This command configures file and directory permissions to allow libvirt
    system mode (qemu:///system) to access CyRIS-created virtual machine disks.
    
    This is automatically done when creating VMs, but this command can be used to:
    - Fix permission issues manually
    - Set up permissions before first use
    - Check system compatibility
    
    Examples:
      cyris setup-permissions           # Set up permissions
      cyris setup-permissions --dry-run # Show what would be done
    """
    config: CyRISSettings = get_config(ctx)
    verbose = ctx.obj.get('verbose', False)
    
    click.echo("Setting up libvirt permissions for CyRIS environment...")
    
    try:
        from ..infrastructure.permissions import PermissionManager
        
        manager = PermissionManager(dry_run=dry_run)
        
        if dry_run:
            click.echo("DRY RUN MODE - No changes will be made")
        
        # Check system compatibility first
        compat_info = manager.check_libvirt_compatibility()
        
        click.echo(f"INFO: Detected libvirt user: {compat_info['libvirt_user'] or 'Not found'}")
        click.echo(f"INFO: ACL support: {'[OK]' if compat_info['acl_supported'] else '[ERROR]'}")
        click.echo(f"INFO: Current user groups: {', '.join(compat_info['current_user_groups'])}")
        
        if compat_info['recommendations']:
            click.echo("\n💡 Recommendations:")
            for rec in compat_info['recommendations']:
                click.echo(f"   • {rec}")
        
        if not compat_info['libvirt_user']:
            click.echo("[ERROR] No libvirt user found. Please install libvirt-daemon-system.")
            sys.exit(1)
        
        if not compat_info['acl_supported']:
            click.echo("[ERROR] ACL commands not found. Please install the 'acl' package.")
            sys.exit(1)
        
        click.echo("\n🔧 Setting up permissions...")
        
        # Set up permissions for CyRIS environment
        success = manager.setup_cyris_environment(config.cyris_path)
        
        if success:
            click.echo("[OK] Successfully configured libvirt permissions")
            click.echo("\n💡 You can now use bridge networking with:")
            click.echo("   cyris create --network-mode bridge --enable-ssh examples/basic.yml")
        else:
            click.echo("WARNING:  Some permission configurations failed")
            click.echo("   Check the verbose output for details")
            if not verbose:
                click.echo("   Run with --verbose for more information")
            sys.exit(1)
            
    except ImportError as e:
        click.echo(f"[ERROR] Failed to import permission manager: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"[ERROR] Error setting up permissions: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()