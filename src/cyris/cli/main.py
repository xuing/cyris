#!/usr/bin/env python3
"""
CyRIS Modern Command Line Interface - Performance Optimized
Startup time optimized with lazy imports and minimal initialization overhead.
"""
import sys
import click
from pathlib import Path
from typing import Optional
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger, get_main_debug_log_path

# Performance optimization: Use lazy imports for heavy modules
# Only import configuration parsing when actually needed

# Initialize unified debug log path
debug_log_path = get_main_debug_log_path()


# Note: logging module replaced with unified logger system


def get_settings_lazy():
    """Lazy import and create settings to improve startup time"""
    from ..config.settings import CyRISSettings
    return CyRISSettings()


def parse_config_lazy(config_path: Path):
    """Lazy import configuration parsing to improve startup time"""
    from ..config.parser import parse_modern_config, ConfigurationError
    try:
        return parse_modern_config(config_path)
    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)


def get_config(ctx):
    """Get configuration from context with fallback (lazy loading)"""
    if ctx.obj is None:
        ctx.obj = {'config': get_settings_lazy()}
    elif 'config' not in ctx.obj:
        ctx.obj['config'] = get_settings_lazy()
    return ctx.obj['config']


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--version', is_flag=True, help='Show version information')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool, version: bool):
    """CyRIS - Modern Cyber Security Training Environment Deployment Tool"""
    
    with open(debug_log_path, 'a') as f:
        f.write(f"[DEBUG] cli() called with config={config}, verbose={verbose}, version={version}\n")
        f.flush()
    
    if version:
        with open(debug_log_path, 'a') as f:
            f.write("[DEBUG] Showing version\n")
            f.flush()
        click.echo("CyRIS v1.4.0 - Cyber Range Instantiation System")
        ctx.exit()
    
    # Initialize context
    with open(debug_log_path, 'a') as f:
        f.write("[DEBUG] Initializing context\n")
        f.flush()
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # Load configuration (optimized for fast startup)
    with open(debug_log_path, 'a') as f:
        f.write("[DEBUG] Loading configuration\n")
        f.flush()
    
    try:
        if config:
            with open(debug_log_path, 'a') as f:
                f.write(f"[DEBUG] Using provided config: {config}\n")
                f.flush()
            config_path = Path(config)
            settings = parse_config_lazy(config_path)
        else:
            with open(debug_log_path, 'a') as f:
                f.write("[DEBUG] Looking for default config files\n")
                f.flush()
            # Try default locations (minimal filesystem access)
            default_configs = [
                Path.cwd() / 'config.yml',
                Path.cwd() / 'config.yaml', 
                Path.cwd() / 'CONFIG'
            ]
            
            settings = None
            for config_path in default_configs:
                with open(debug_log_path, 'a') as f:
                    f.write(f"[DEBUG] Checking config file: {config_path}\n")
                    f.flush()
                if config_path.exists():
                    with open(debug_log_path, 'a') as f:
                        f.write(f"[DEBUG] Found config file: {config_path}, parsing...\n")
                        f.flush()
                    settings = parse_config_lazy(config_path)
                    break
            
            if settings is None:
                with open(debug_log_path, 'a') as f:
                    f.write("[DEBUG] No config file found, using default settings\n")
                    f.flush()
                settings = get_settings_lazy()
        
        with open(debug_log_path, 'a') as f:
            f.write("[DEBUG] Configuration loaded successfully\n")
            f.flush()
        ctx.obj['config'] = settings
        
        with open(debug_log_path, 'a') as f:
            f.write("[DEBUG] cli() function completed successfully\n")
            f.flush()
        
    except Exception as e:
        with open(debug_log_path, 'a') as f:
            f.write(f"[DEBUG] Exception in cli(): {e}\n")
            f.flush()
        from ..config.parser import ConfigurationError
        if isinstance(e, ConfigurationError):
            click.echo(f"Configuration error: {e}", err=True)
        else:
            click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('description_file', type=click.Path(exists=True, path_type=Path))
@click.option('--range-id', type=int, help='Specify cyber range ID')
@click.option('--dry-run', is_flag=True, help='Dry run mode, do not actually create')
@click.option('--build-only', is_flag=True, help='Build images only, do not create VMs (saves to build_storage_dir)')
@click.option('--skip-builder', is_flag=True, help='Skip image building, use existing images in build_storage_dir')
@click.option('--network-mode', 
              type=click.Choice(['user', 'bridge'], case_sensitive=False),
              default='bridge',
              help='Network mode: user (isolated) or bridge (SSH accessible)')
@click.option('--enable-ssh', is_flag=True, default=True, help='Enable SSH access (requires bridge networking)')
@click.option('--recreate', is_flag=True, help='Force recreate existing range (destroy and rebuild)')
@click.pass_context
def create(ctx, description_file: Path, range_id: Optional[int], dry_run: bool, build_only: bool, skip_builder: bool, network_mode: str, enable_ssh: bool, recreate: bool):
    """Create a new cyber range
    
    DESCRIPTION_FILE: YAML format cyber range description file
    """
    with open(debug_log_path, 'a') as f:
        f.write(f"[DEBUG] create() called with file={description_file}, dry_run={dry_run}, build_only={build_only}, skip_builder={skip_builder}\n")
        f.flush()
    
    # Validate mutually exclusive options
    if build_only and skip_builder:
        click.echo("Error: --build-only and --skip-builder cannot be used together", err=True)
        sys.exit(1)
    
    from .commands import CreateCommandHandler
    
    with open(debug_log_path, 'a') as f:
        f.write("[DEBUG] Imported CreateCommandHandler\n")
        f.flush()
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    with open(debug_log_path, 'a') as f:
        f.write("[DEBUG] Got config and verbose, creating handler\n")
        f.flush()
    
    handler = CreateCommandHandler(config, verbose)
    
    with open(debug_log_path, 'a') as f:
        f.write("[DEBUG] About to call handler.execute()\n")
        f.flush()
    
    success = handler.execute(
        description_file=description_file,
        range_id=range_id,
        dry_run=dry_run,
        build_only=build_only,
        skip_builder=skip_builder,
        network_mode=network_mode,
        enable_ssh=enable_ssh,
        recreate=recreate
    )
    
    with open(debug_log_path, 'a') as f:
        f.write(f"[DEBUG] handler.execute() returned: {success}\n")
        f.flush()
    
    if not success:
        sys.exit(1)


@cli.command()
@click.option('--range-id', type=int, help='Cyber range ID')
@click.option('--all', 'list_all', is_flag=True, help='Show all cyber ranges')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information including VM IPs')
@click.pass_context
def list(ctx, range_id: Optional[int], list_all: bool, verbose: bool):
    """List cyber ranges"""
    from .commands import ListCommandHandler
    
    config = get_config(ctx)
    ctx_verbose = ctx.obj['verbose']
    
    handler = ListCommandHandler(config, ctx_verbose)
    success = handler.execute(
        range_id=str(range_id) if range_id else None,
        list_all=list_all,
        verbose=verbose
    )
    
    if not success:
        sys.exit(1)


@cli.command()
@click.argument('range_id')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information including VM IPs')
@click.pass_context
def status(ctx, range_id: str, verbose: bool):
    """Display cyber range status
    
    RANGE_ID: Cyber range ID
    """
    from .commands import StatusCommandHandler
    
    config = get_config(ctx)
    ctx_verbose = ctx.obj['verbose']
    
    handler = StatusCommandHandler(config, ctx_verbose)
    success = handler.execute(range_id=range_id, verbose=verbose)
    
    if not success:
        sys.exit(1)


@cli.command()
@click.argument('range_id')
@click.option('--force', '-f', is_flag=True, help='Force deletion without confirmation')
@click.option('--rm', is_flag=True, help='Remove all records after destroying (like docker run --rm)')
@click.pass_context
def destroy(ctx, range_id: str, force: bool, rm: bool):
    """Destroy the specified cyber range (stops VMs, cleans up resources)
    
    RANGE_ID: ID of the cyber range to destroy
    """
    from .commands import DestroyCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = DestroyCommandHandler(config, verbose)
    success = handler.execute(range_id=range_id, force=force, rm=rm)
    
    if not success:
        sys.exit(1)


@cli.command()
@click.argument('range_id')
@click.option('--force', '-f', is_flag=True, help='Force removal even if range is not destroyed')
@click.pass_context
def rm(ctx, range_id: str, force: bool):
    """Remove a cyber range completely from the system
    
    RANGE_ID: ID of the cyber range to remove
    """
    from .commands import DestroyCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = DestroyCommandHandler(config, verbose)
    success = handler.remove_range(range_id=range_id, force=force)
    
    if not success:
        sys.exit(1)


@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    from .commands import ConfigCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = ConfigCommandHandler(config, verbose)
    handler.execute(action='show')


@cli.command()
@click.option('--output', '-o', type=click.Path(path_type=Path), default='config.yml', 
              help='Output configuration file path')
@click.pass_context
def config_init(ctx, output: Path):
    """Initialize default configuration file"""
    from .commands import ConfigCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = ConfigCommandHandler(config, verbose)
    success = handler.execute(action='init', output_path=output)
    
    if not success:
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate environment configuration and dependencies"""
    config = get_config(ctx)
    
    click.echo("Validating CyRIS environment...")
    errors = 0
    
    # Check paths
    if not config.cyris_path.exists():
        click.echo(f"[ERROR] CyRIS path does not exist: {config.cyris_path}", err=True)
        errors += 1
    else:
        click.echo(f"[OK] CyRIS path: {config.cyris_path}")
    
    if not config.cyber_range_dir.exists():
        click.echo(f"[ERROR] Cyber range directory does not exist: {config.cyber_range_dir}", err=True)
        errors += 1
    else:
        click.echo(f"[OK] Cyber range directory: {config.cyber_range_dir}")
    
    # Check libvirt availability
    try:
        import libvirt
        click.echo(f"[OK] libvirt Python bindings available")
    except ImportError:
        click.echo(f"[WARNING] libvirt Python bindings not available - VM operations may fail", err=True)
        click.echo("  Install with: pip install libvirt-python", err=True)
    
    # Check virsh command availability (fallback)
    try:
        import subprocess
        result = subprocess.run(['virsh', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            click.echo(f"[OK] virsh command available")
        else:
            click.echo(f"[WARNING] virsh command not working properly", err=True)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        click.echo(f"[WARNING] virsh command not found - install libvirt-clients", err=True)
    except Exception as e:
        click.echo(f"[WARNING] Error checking virsh: {e}", err=True)
    
    if errors == 0:
        click.echo("🎉 Environment validation passed!")
    else:
        click.echo(f"[ERROR] Found {errors} issues", err=True)
        sys.exit(1)


@cli.command(name='ssh-info')
@click.argument('range_id', type=str)
@click.pass_context
def ssh_info(ctx, range_id: str):
    """Get SSH connection information for a cyber range"""
    from .commands import SSHInfoCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = SSHInfoCommandHandler(config, verbose)
    success = handler.execute(range_id=range_id)
    
    if not success:
        sys.exit(1)


@cli.command(name='setup-permissions')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
@click.pass_context
def setup_permissions(ctx, dry_run: bool):
    """Set up libvirt permissions for CyRIS environment"""
    from .commands import PermissionsCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = PermissionsCommandHandler(config, verbose)
    success = handler.execute(dry_run=dry_run)
    
    if not success:
        sys.exit(1)


@cli.command(name='legacy')
@click.argument('args', nargs=-1)
@click.pass_context
def legacy_run(ctx, args):
    """Run legacy CyRIS commands (compatibility mode)"""
    from .commands import LegacyCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = LegacyCommandHandler(config, verbose)
    success = handler.execute(args=args)
    
    if not success:
        sys.exit(1)


def main(args=None):
    """Main entry point"""
    logger = None
    try:
        logger = get_logger(__name__, "cli_main")
    except Exception as logger_error:
        # If logger creation fails, continue without logging to avoid masking the real error
        with open(debug_log_path, 'a') as f:
            f.write(f"[DEBUG] Logger creation failed: {logger_error}\n")
            f.flush()
    
    with open(debug_log_path, 'a') as f:
        f.write(f"[DEBUG] CLI main() called with args: {args}\n")
        f.flush()
    
    if logger:
        logger.debug(f"CLI main() called with args: {args}")
    
    try:
        with open(debug_log_path, 'a') as f:
            f.write("[DEBUG] About to call cli()...\n")
            f.flush()
        if logger:
            logger.debug("About to call cli()...")
        cli(args)
        if logger:
            logger.debug("cli() completed successfully")
        with open(debug_log_path, 'a') as f:
            f.write("[DEBUG] cli() completed successfully\n")
            f.flush()
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        with open(debug_log_path, 'a') as f:
            f.write(f"[DEBUG] Exception in main(): {e}\n")
            f.flush()
        # Safe logger usage with fallback
        if logger:
            try:
                logger.error(f"Exception in main(): {e}")
            except Exception:
                # If logger fails, just continue without logging
                pass
        click.echo(f"[ERROR] Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()