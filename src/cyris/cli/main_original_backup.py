#!/usr/bin/env python3
"""
CyRIS Modern Command Line Interface
Supports modern commands while maintaining backward compatibility
"""
import sys
import click
from pathlib import Path
from typing import Optional, Any, IO
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import locale
import os

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape
from rich.status import Status
from rich import print as rich_print

from ..config.parser import parse_modern_config, ConfigurationError
from ..config.settings import CyRISSettings


# Disable logging to prevent output mixing - Rich handles all output
logging.disable(logging.CRITICAL)

# Create Rich consoles following best practices
console = Console()
error_console = Console(stderr=True, style="bold red")
logger = get_logger(__name__, "main_original_backup")


# Rich-based status indicators using proper Text objects
def get_status_text(status: str, label: str = None) -> Text:
    """Get Rich Text object with appropriate styling for status"""
    status_lower = status.lower()
    label_text = escape(label or status)  # Always escape text content
    
    # Use Rich emoji names and proper styling
    styles = {
        'active': (':green_circle:', 'green'),
        'creating': (':yellow_circle:', 'yellow'), 
        'error': (':red_circle:', 'red'),
        'ok': (':check_mark:', 'green'),
        'fail': (':cross_mark:', 'red'),
        'warning': (':warning:', 'orange3'),
        'info': (':information:', 'blue'),
        'running': (':arrow_forward:', 'green'),
        'stopped': (':stop_button:', 'red'),
        'healthy': (':green_heart:', 'green'),
        'unhealthy': (':cross_mark:', 'red')
    }
    
    if status_lower in styles:
        emoji, color = styles[status_lower]
        # Create Text object with proper emoji handling using Text.assemble
        return Text.assemble(
            (emoji, color),
            (" ", ""),
            (label_text, color)
        )
    else:
        return Text.assemble(
            ("•", "dim"),
            (" ", ""),
            (label_text, "dim")
        )


# Simple output - just use click.echo directly, no need for complex wrapper


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
    
    # Logging is disabled globally for clean CLI output
    
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
    
    console.print(Text.assemble(
        ("Creating cyber range:", "bold blue"),
        (" ", ""),
        (str(description_file), "cyan")
    ))
    
    if verbose:
        console.print(Text.assemble(
            ("Configuration:", "dim"),
            (" ", ""),
            (str(config), "yellow")
        ))
        console.print(Text.assemble(
            ("Range ID:", "dim"),
            (" ", ""),
            (str(range_id or 'auto-assigned'), "cyan")
        ))
    
    if dry_run:
        console.print(Text("Dry run mode - will not actually create cyber range", style="bold yellow"))
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
                console.print(Text.assemble(
                    ("[OK] ", "bold green"),
                    ("Validation successful. Would create range: ", "green"),
                    (str(result), "cyan")
                ))
            else:
                error_console.print(Text("Validation failed", style="bold red"))
                sys.exit(1)
        except Exception as e:
            error_console.print(Text.assemble(
                ("Validation error: ", "bold red"),
                (escape(str(e)), "red")
            ))
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
        console.print(Text("Initializing cyber range creation...", style="bold blue"))
        result = orchestrator.create_range_from_yaml(
            description_file=description_file,
            range_id=range_id,
            dry_run=dry_run
        )
        
        if result:
            console.print(Text.assemble(
                ("[OK] ", "bold green"),
                ("Cyber range created successfully: ", "green"),
                (str(result), "cyan")
            ))
        else:
            error_console.print(Text("[ERROR] Cyber range creation failed", style="bold red"))
            sys.exit(1)
            
    except Exception as e:
        error_console.print(Text.assemble(
            ("[ERROR] Error creating cyber range: ", "bold red"),
            (str(e), "red")
        ))
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
            console.print(Text.assemble(
                ("Cyber range ", "bold blue"),
                (range_id, "bold cyan"),
                (" details:", "bold blue")
            ))
            range_metadata = orchestrator.get_range(range_id)
            if range_metadata:
                console.print(Text.assemble(
                    ("  Name: ", "dim"),
                    (range_metadata.name, "cyan")
                ))
                status_text = get_status_text(range_metadata.status.value, range_metadata.status.value.upper())
                console.print(Text.assemble(
                    ("  Status: ", "dim"),
                    status_text
                ))
                console.print(Text.assemble(
                    ("  Created: ", "dim"),
                    (str(range_metadata.created_at), "green")
                ))
                console.print(Text.assemble(
                    ("  Description: ", "dim"),
                    (escape(range_metadata.description), "white")
                ))
                if range_metadata.tags:
                    console.print(Text.assemble(
                        ("  Tags: ", "dim"),
                        (str(range_metadata.tags), "yellow")
                    ))
            else:
                error_console.print(Text.assemble(
                    ("  Range ", "bold red"),
                    (range_id, "red"),
                    (" not found in orchestrator", "bold red")
                ))
        else:
            # List ranges
            ranges = orchestrator.list_ranges()
            
            if not ranges:
                console.print(Text("No cyber ranges found in orchestrator", style="yellow"))
                
                # Fallback: Check filesystem for range directories  
                ranges_dir = config.cyber_range_dir
                if ranges_dir.exists():
                    range_dirs = [d for d in ranges_dir.iterdir() if d.is_dir()]
                    if range_dirs:
                        console.print(Text.assemble(
                            ("Found ", "dim"),
                            (str(len(range_dirs)), "cyan"),
                            (" range directories on filesystem:", "dim")
                        ))
                        for range_dir in sorted(range_dirs):
                            console.print(Text.assemble(
                                ("  ", ""),
                                (range_dir.name, "cyan"),
                                (" (filesystem only)", "dim")
                            ))
                else:
                    error_console.print(Text.assemble(
                        ("Cyber range directory does not exist: ", "bold red"),
                        (str(ranges_dir), "red")
                    ))
                
                # Check for running VMs that might be orphaned
                _check_running_vms(provider)
                return
            
            # Display orchestrated ranges using Rich markup properly
            filter_text = "all" if list_all else "active only"
            console.print(Text.assemble(
                ("\n", ""),
                ("Cyber Ranges", "bold blue"),
                (" (", "dim"),
                (filter_text, "dim"),
                (")", "dim")
            ))
            
            displayed_count = 0
            for range_meta in sorted(ranges, key=lambda r: r.created_at):
                if not list_all and range_meta.status.value not in ['active', 'creating']:
                    continue
                    
                displayed_count += 1
                
                # Create status indicator using Rich Text
                status_text = get_status_text(range_meta.status.value, range_meta.status.value.upper())
                
                # Range header with status - use Rich Text.assemble for safety
                header = Text.assemble(
                    ("  ", ""),
                    status_text,
                    (" ", ""),
                    (str(range_meta.range_id), "bold"),
                    (": ", "bold"),
                    (escape(range_meta.name), "")
                )
                console.print(header)
                
                # Range details with proper escaping
                console.print(Text.assemble(
                    (" ", ""),
                    ("Created:", "dim"),
                    (" ", ""),
                    (range_meta.created_at.strftime('%Y-%m-%d %H:%M'), "")
                ))
                if range_meta.description:
                    console.print(Text.assemble(
                        (" ", ""),
                        ("Description:", "dim"),
                        (" ", ""),
                        (escape(range_meta.description), "")
                    ))
                
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
                            
                            vm_texts = []
                            has_issues = False
                            
                            for guest in resources['guests']:
                                try:
                                    health_info = ip_manager.get_vm_health_info(guest)
                                    
                                    # Create Rich Text for VM status
                                    if health_info.is_healthy:
                                        label = f"{guest}: {health_info.get_compact_status()}"
                                        vm_text = get_status_text('healthy', label)
                                    else:
                                        label = f"{guest}: {health_info.get_compact_status()}"
                                        vm_text = get_status_text('unhealthy', label)
                                        has_issues = True
                                    
                                    vm_texts.append(vm_text)
                                        
                                except Exception:
                                    label = f"{guest}: check failed"
                                    vm_text = get_status_text('error', label)
                                    vm_texts.append(vm_text)
                                    has_issues = True
                            
                            if vm_texts:
                                # Display VMs in a clean format
                                console.print(Text(" VMs:", style="bold"))
                                for vm_text in vm_texts:
                                    console.print(Text.assemble(
                                        ("   ", ""),
                                        vm_text
                                    ))
                                
                                # Show hint if there are issues
                                if has_issues:
                                    console.print(Text.assemble(
                                        (" ", ""),
                                        ("💡 Issues detected - use 'cyris status ", "yellow"),
                                        (str(range_meta.range_id), "yellow"),
                                        (" --verbose' for details", "yellow")
                                    ))
                            
                            ip_manager.close()
                            
                        except ImportError:
                            console.print(" [yellow]⚠️  VM status checking not available[/yellow]")
                        except Exception:
                            pass  # Silently skip health check errors in list mode
            
            if displayed_count == 0:
                console.print("  [dim]No ranges match the filter criteria[/dim]")
        
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

    console.print(f"\n[bold blue]Cyber Range Status[/bold blue]: [bold]{range_id}[/bold]")

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
            # Create a beautiful info table using Rich
            table = Table(show_header=False, show_edge=False, padding=(0, 1))
            table.add_column("Field", style="dim", width=15)
            table.add_column("Value")

            # Add status with proper Rich Text object
            status_text = get_status_text(range_metadata.status.value, range_metadata.status.value.upper())
            table.add_row("Status", status_text)

            # Use Rich markup safely with escape
            name_text = Text(escape(range_metadata.name), style="bold")
            table.add_row("Name", name_text)
            table.add_row("Description", escape(range_metadata.description))
            table.add_row("Created", range_metadata.created_at.strftime('%Y-%m-%d %H:%M:%S'))
            table.add_row("Last Modified", range_metadata.last_modified.strftime('%Y-%m-%d %H:%M:%S'))

            if range_metadata.owner:
                table.add_row("Owner", escape(range_metadata.owner))

            if range_metadata.tags:
                # Create tags text safely
                tags_text = Text()
                for i, (k, v) in enumerate(range_metadata.tags.items()):
                    if i > 0:
                        tags_text.append(", ")
                    tags_text.append(escape(k), style="cyan")
                    tags_text.append("=")
                    tags_text.append(escape(str(v)))
                table.add_row("Tags", tags_text)

            console.print(table)

            # Show resource information
            resources = orchestrator.get_range_resources(range_id)
            if resources:
                console.print(f"\n[bold]Resources:[/bold]")
                if resources.get('hosts'):
                    console.print(f"  Hosts: [green]{len(resources['hosts'])}[/green]")
                if resources.get('guests'):
                    console.print(f"  Guests: [green]{len(resources['guests'])}[/green]")

                    # Show VM health information using Rich Panel
                    if resources.get('guests') and verbose:
                        vm_panel_content = []

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

                                    # Create VM info table using Rich best practices
                                    vm_table = Table(show_header=False, show_edge=False, padding=(0, 1), width=80)
                                    vm_table.add_column("Field", style="dim", width=12)
                                    vm_table.add_column("Value")

                                    # Use Text.assemble for complex content
                                    libvirt_text = Text(health_info.libvirt_status, style="cyan")
                                    vm_table.add_row("Libvirt", libvirt_text)

                                    healthy_text = Text("Yes", style="green") if health_info.is_healthy else Text("No", style="red")
                                    vm_table.add_row("Healthy", healthy_text)

                                    if health_info.ip_addresses:
                                        # Use Text.assemble for IP addresses properly
                                        ip_parts = []
                                        for i, ip in enumerate(health_info.ip_addresses):
                                            if i > 0:
                                                ip_parts.append((", ", "dim"))
                                            ip_parts.append((ip, "green"))
                                        ip_text = Text.assemble(*ip_parts)
                                        vm_table.add_row("IP Address", ip_text)

                                        network_text = Text.assemble(
                                            (":check_mark: ", "green"),
                                            ("Reachable", "green")
                                        ) if health_info.network_reachable else Text.assemble(
                                            (":warning: ", "yellow"),
                                            ("Not reachable", "yellow")
                                        )
                                        vm_table.add_row("Network", network_text)
                                    else:
                                        vm_table.add_row("IP Address", Text("Not assigned", style="dim"))

                                    if health_info.uptime:
                                        vm_table.add_row("Uptime", health_info.uptime)

                                    if health_info.disk_path:
                                        vm_table.add_row("Disk", Text(health_info.disk_path, style="dim"))

                                    # Create VM Panel with status indicator using Rich Text.assemble
                                    vm_status_icon = ":green_heart:" if health_info.is_healthy else ":cross_mark:"
                                    panel_title_text = Text.assemble(
                                        (vm_status_icon, "green" if health_info.is_healthy else "red"),
                                        (" ", ""),
                                        (guest, "bold")
                                    )

                            # Create error details if any
                                    panel_content = [vm_table]
                                    if health_info.error_details:
                                        # Create error details table with automatic text wrapping
                                        error_table = Table(show_header=False, show_edge=False, padding=(0, 0, 0, 1))
                                        error_table.add_column("", style="red", width=3, no_wrap=True)
                                        error_table.add_column("Error Details", overflow="fold")

                                        error_table.add_row("", Text("Error Details:", style="bold red"))

                                        for i, error in enumerate(health_info.error_details, 1):
                                            error_table.add_row(f"{i}.", error)

                                        panel_content.append(error_table)

                                    # Create Panel for this VM with auto-wrapping support
                                    from rich.console import Group
                                    vm_panel = Panel(
                                        Group(*panel_content),
                                        title=panel_title_text,
                                        expand=False,
                                        border_style="red" if not health_info.is_healthy else "green"
                                    )
                                    console.print(vm_panel)

                                except Exception as e:
                                    pass
                                    error_console.print(Text.assemble(
                                        ("[ERROR] ", "bold red"),
                                        (guest, "red"),
                                        (": Health check failed - ", "red"),
                                        (str(e), "red")
                                    ))

                            ip_manager.close()

                        except ImportError:
                            console.print(Text("WARNING:  VM health checking not available", style="yellow"))
                        except Exception as e:
                            pass
                            error_console.print(Text.assemble(
                                ("[ERROR] Health check error: ", "bold red"),
                                (str(e), "red")
                            ))

                    elif resources.get('guests'):
                        console.print(Text("💡 Use --verbose to see detailed VM health status", style="blue"))

        else:
            error_console.print(Text("  [ERROR] Range not found in orchestrator", style="bold red"))

        # Add visual separator before filesystem section
        console.print()  # Empty line for spacing

        # Check filesystem regardless
        range_dir = config.cyber_range_dir / range_id

        if range_dir.exists():
            # Simple directory display following Rich best practices
            console.print(Text.assemble(
                ("Directory:", "dim"),
                (" ", ""),
                (str(range_dir), "cyan")
            ))

            # Show directory contents if verbose - simplified display
            if verbose:
                try:
                    contents = []
                    for item in range_dir.iterdir():
                        contents.append(item)

                    if contents:
                        console.print(Text.assemble(
                            ("Contents (", "dim"),
                            (str(len(contents)), "cyan"),
                            (" items):", "dim")
                        ))
                        for item in sorted(contents):
                            icon = "📁" if item.is_dir() else "📄"
                            style = "yellow" if item.is_dir() else "white"
                            console.print(Text.assemble(
                                ("  ", ""),
                                (icon, style),
                                (" ", ""),
                                (item.name, style)
                            ))
                    else:
                        console.print(Text("  (empty directory)", style="dim italic"))

                except Exception as e:
                    error_console.print(Text.assemble(
                        ("Could not list directory contents: ", "red"),
                        (str(e), "red")
                    ))
        else:
            if not range_metadata:
                error_console.print(Text.assemble(
                    ("  [ERROR] Range ", "bold red"),
                    (range_id, "bold red"),
                    (" not found (no orchestrator record, no filesystem directory)", "bold red")
                ))
                sys.exit(1)
            else:
                console.print(Text("  WARNING:  Range exists in orchestrator but no filesystem directory found", style="yellow"))

    except Exception as e:
        error_console.print(Text.assemble(
            ("[ERROR] Error checking range status: ", "bold red"),
            (str(e), "red")
        ))
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    config: CyRISSettings = get_config(ctx)
    
    console.print(Text("Current configuration:", style="bold blue"))
    console.print(Text.assemble(
        ("  CyRIS path: ", "dim"),
        (str(config.cyris_path), "cyan")
    ))
    console.print(Text.assemble(
        ("  Cyber range directory: ", "dim"),
        (str(config.cyber_range_dir), "cyan")
    ))
    console.print(Text.assemble(
        ("  Gateway mode: ", "dim"),
        ("enabled" if config.gw_mode else "disabled", "green" if config.gw_mode else "red")
    ))
    
    if config.gw_account:
        console.print(Text.assemble(
            ("  Gateway account: ", "dim"),
            (config.gw_account, "yellow")
        ))
    if config.gw_mgmt_addr:
        console.print(Text.assemble(
            ("  Gateway management address: ", "dim"),
            (config.gw_mgmt_addr, "yellow")
        ))
    if config.user_email:
        console.print(Text.assemble(
            ("  User email: ", "dim"),
            (config.user_email, "yellow")
        ))


@cli.command()
@click.option('--output', '-o', type=click.Path(path_type=Path), 
              default='config.yml', help='Output configuration file path')
@click.pass_context
def config_init(ctx, output: Path):
    """Initialize default configuration file"""
    if output.exists():
        if not click.confirm(f'Configuration file {output} already exists. Overwrite?'):
            console.print(Text('Operation cancelled', style="yellow"))
            return
    
    # Create default configuration
    from ..config.parser import create_default_config
    
    try:
        settings = create_default_config(output)
        console.print(Text.assemble(
            ("[OK] ", "bold green"),
            ("Default configuration file created: ", "green"),
            (str(output), "cyan")
        ))
        console.print(Text("Please edit the configuration file to suit your environment", style="dim"))
    except Exception as e:
        error_console.print(Text.assemble(
            ("[ERROR] Failed to create configuration file: ", "bold red"),
            (str(e), "red")
        ))


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate environment configuration and dependencies"""
    console.print(Text("Validating CyRIS environment...", style="bold blue"))
    
    config: CyRISSettings = get_config(ctx)
    errors = 0
    
    # Check paths
    if not config.cyris_path.exists():
        error_console.print(Text.assemble(
            ("[ERROR] CyRIS path does not exist: ", "bold red"),
            (str(config.cyris_path), "red")
        ))
        errors += 1
    else:
        console.print(Text.assemble(
            ("[OK] ", "bold green"),
            ("CyRIS path: ", "green"),
            (str(config.cyris_path), "cyan")
        ))
    
    if not config.cyber_range_dir.exists():
        error_console.print(Text.assemble(
            ("[ERROR] Cyber range directory does not exist: ", "bold red"),
            (str(config.cyber_range_dir), "red")
        ))
        errors += 1
    else:
        console.print(Text.assemble(
            ("[OK] ", "bold green"),
            ("Cyber range directory: ", "green"),
            (str(config.cyber_range_dir), "cyan")
        ))
    
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
        console.print(Text("🎉 Environment validation passed!", style="bold green"))
    else:
        error_console.print(Text.assemble(
            ("[ERROR] Found ", "bold red"),
            (str(errors), "red"),
            (" issues", "bold red")
        ))
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
            error_console.print(Text.assemble(
                ("[ERROR] Range ", "bold red"),
                (range_id, "red"),
                (" not found", "bold red")
            ))
            sys.exit(1)
        
        # Get range resources
        resources = orchestrator.get_range_resources(range_id)
        if not resources or not resources.get('guests'):
            error_console.print(Text.assemble(
                ("[ERROR] No VMs found for range ", "bold red"),
                (range_id, "red")
            ))
            sys.exit(1)
        
        console.print(Text.assemble(
            ("SSH Connection Information for Range ", "bold blue"),
            (range_id, "bold cyan"),
            (":", "bold blue")
        ))
        console.print(Text.assemble(
            ("Range Name: ", "dim"),
            (escape(range_metadata.name), "cyan")
        ))
        status_text = get_status_text(range_metadata.status.value, range_metadata.status.value)
        console.print(Text.assemble(
            ("Status: ", "dim"),
            status_text
        ))
        console.print("=" * 60)
        
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
            console.print(Text.assemble(
                ("\nVM: ", "bold magenta"),
                ("VM: ", "bold blue"),
                (vm_id, "cyan")
            ))
            
            # Get comprehensive health information
            vm_ip_addresses = []
            if ip_manager:
                try:
                    health_info = ip_manager.get_vm_health_info(vm_id)
                    
                    # Smart status indicators using Rich Text
                    status_text = get_status_text('ok', 'Status') if health_info.is_healthy else get_status_text('error', 'Status')
                    
                    console.print(Text.assemble(
                        ("   ", ""),
                        status_text,
                        (": ", ""),
                        (health_info.libvirt_status, "cyan"),
                        (" → ", "dim"),
                        ("healthy" if health_info.is_healthy else "unhealthy", "green" if health_info.is_healthy else "red")
                    ))
                    
                    if health_info.ip_addresses:
                        vm_ip_addresses = health_info.ip_addresses
                        ip_text = Text.assemble(
                            ("   IP: IP Addresses: ", "blue"),
                            *[((", " if i > 0 else "") + ip, "green") for i, ip in enumerate(vm_ip_addresses)]
                        )
                        console.print(ip_text)
                        
                        if health_info.network_reachable:
                            console.print(Text("   NET: Network: Reachable [OK]", style="green"))
                        else:
                            console.print(Text("   NET: Network: Not reachable WARNING:", style="yellow"))
                        
                        # Show direct SSH commands only if healthy
                        if health_info.is_healthy:
                            console.print(Text("   SSH: SSH Commands:", style="blue"))
                            for ip in vm_ip_addresses:
                                console.print(Text.assemble(
                                    ("  ssh user@", "cyan"),
                                    (ip, "green")
                                ))
                                console.print(Text.assemble(
                                    ("  ssh root@", "cyan"),
                                    (ip, "green"),
                                    ("  # if root access is configured", "dim")
                                ))
                        else:
                            console.print(Text("   WARNING:  SSH may not be available due to VM issues", style="yellow"))
                    else:
                        console.print(Text("   IP: IP Address: Not assigned", style="dim"))
                    
                    # Show uptime if available
                    if health_info.uptime:
                        console.print(Text.assemble(
                            ("   TIME:  Uptime: ", "blue"),
                            (health_info.uptime, "cyan")
                        ))
                    
                    # Show disk path if available
                    if health_info.disk_path:
                        console.print(Text.assemble(
                            ("   DISK: Disk: ", "blue"),
                            (health_info.disk_path, "dim")
                        ))
                    
                    # Show all error details directly
                    if health_info.error_details:
                        console.print(Text("   INFO: Error Details:", style="blue"))
                        for i, error in enumerate(health_info.error_details, 1):
                            # Use Rich automatic text wrapping with overflow="fold"
                            console.print(Text.assemble(
                                ("  ", ""),
                                (str(i), "red"),
                                (". ", "red"),
                                (error, "")
                            ), overflow="fold")
                            
                except Exception as e:
                    error_console.print(Text.assemble(
                        ("   [ERROR] Health check failed: ", "bold red"),
                        (str(e), "red")
                    ))
            
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
                            click.echo(f"  {cmd}")
                
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
        
        console.print(Text("\n💡 Tips:", style="bold blue"))
        console.print(Text("   • For bridge networking, VMs get DHCP IP addresses", style="dim"))
        console.print(Text("   • Use 'nmap -sP 192.168.122.0/24' to scan for active IPs", style="dim"))
        console.print(Text("   • VNC console is available on all VMs for direct access", style="dim"))
        
    except Exception as e:
        error_console.print(Text.assemble(
            ("[ERROR] Error getting SSH info: ", "bold red"),
            (str(e), "red")
        ))
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