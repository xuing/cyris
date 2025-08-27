#!/usr/bin/env python3
"""
CyRIS Modern Command Line Interface - Refactored Version
遵循KISS原则：仅保留CLI路由，业务逻辑委托给命令处理器
"""
import sys
import click
from pathlib import Path
from typing import Optional
import logging

from ..config.parser import parse_modern_config, ConfigurationError
from ..config.settings import CyRISSettings


# Disable logging to prevent output mixing
logging.disable(logging.CRITICAL)


def get_config(ctx) -> CyRISSettings:
    """Get configuration from context with fallback"""
    if ctx.obj is None:
        ctx.obj = {'config': CyRISSettings()}
    elif 'config' not in ctx.obj:
        ctx.obj['config'] = CyRISSettings()
    return ctx.obj['config']


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--version', is_flag=True, help='Show version information')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool, version: bool):
    """CyRIS - Modern Cyber Security Training Environment Deployment Tool"""
    
    if version:
        click.echo("CyRIS v1.4.0 - Cyber Range Instantiation System")
        ctx.exit()
    
    # Initialize context
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # Load configuration
    try:
        if config:
            config_path = Path(config)
            settings = parse_modern_config(config_path)
        else:
            # Try default locations
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
                        break
                    except ConfigurationError:
                        continue
            
            if settings is None:
                settings = CyRISSettings()
        
        ctx.obj['config'] = settings
        
    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('description_file', type=click.Path(exists=True, path_type=Path))
@click.option('--range-id', type=int, help='Specify cyber range ID')
@click.option('--dry-run', is_flag=True, help='Dry run mode, do not actually create')
@click.option('--network-mode', type=click.Choice(['user', 'bridge']), default='user', help='Network mode')
@click.option('--enable-ssh', is_flag=True, help='Enable SSH access')
@click.pass_context
def create(ctx, description_file: Path, range_id: Optional[int], dry_run: bool, network_mode: str, enable_ssh: bool):
    """Create a new cyber range"""
    from .commands import CreateCommandHandler
    
    config = get_config(ctx)
    verbose = ctx.obj['verbose']
    
    handler = CreateCommandHandler(config, verbose)
    success = handler.execute(
        description_file=description_file,
        range_id=range_id,
        dry_run=dry_run,
        network_mode=network_mode,
        enable_ssh=enable_ssh
    )
    
    if not success:
        sys.exit(1)


@cli.command()
@click.option('--range-id', type=int, help='Cyber range ID')
@click.option('--all', 'list_all', is_flag=True, help='Show all cyber ranges')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
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
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.pass_context
def status(ctx, range_id: str, verbose: bool):
    """Display cyber range status"""
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
@click.option('--rm', is_flag=True, help='Remove all records after destroying')
@click.pass_context
def destroy(ctx, range_id: str, force: bool, rm: bool):
    """Destroy the specified cyber range"""
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
    """Remove a cyber range completely from the system"""
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
    try:
        cli(args)
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"[ERROR] Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()