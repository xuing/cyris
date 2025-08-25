"""
Destroy和Remove命令处理器
处理靶场销毁和删除逻辑
"""

from .base_command import BaseCommandHandler
from cyris.cli.presentation import MessageFormatter


class DestroyCommandHandler(BaseCommandHandler):
    """Destroy命令处理器 - 销毁靶场"""
    
    def execute(self, range_id: str, force: bool = False, rm: bool = False) -> bool:
        """执行destroy命令"""
        try:
            if not self.validate_range_id(range_id):
                return False
            
            if not force:
                import click
                if not click.confirm(f'Are you sure you want to destroy cyber range {range_id}?'):
                    self.console.print('[yellow]Operation cancelled[/yellow]')
                    return True
            
            self.console.print(f"[bold blue]Destroying cyber range:[/bold blue] {range_id}")
            
            # Get range metadata first to determine correct connection
            basic_orchestrator, _ = self.create_orchestrator()
            if not basic_orchestrator:
                return False
            
            range_metadata = basic_orchestrator.get_range(range_id)
            if not range_metadata:
                self.error_display.display_range_not_found(range_id)
                self._check_legacy_ranges(range_id)
                return False
            
            # Determine correct libvirt connection
            libvirt_uri = self._get_libvirt_uri(range_metadata)
            
            # Create orchestrator with correct connection
            network_mode = 'bridge' if 'system' in libvirt_uri else 'user'
            orchestrator, _ = self.create_orchestrator(network_mode)
            if not orchestrator:
                return False
            
            # Destroy the range
            success = orchestrator.destroy_range(range_id)
            
            if success:
                self.console.print(MessageFormatter.success(
                    f"Cyber range {range_id} destroyed successfully"
                ))
                
                # If --rm flag is set, also remove all records
                if rm:
                    return self._remove_records(orchestrator, range_id, force)
                
                return True
            else:
                self.console.print(MessageFormatter.error(
                    f"Failed to destroy cyber range {range_id}"
                ))
                return False
                
        except Exception as e:
            self.handle_error(e, "destroy")
            return False
    
    def remove_range(self, range_id: str, force: bool = False) -> bool:
        """执行rm命令 - 完全删除靶场"""
        try:
            if not self.validate_range_id(range_id):
                return False
            
            # Safety confirmation
            import click
            range_desc = f"cyber range {range_id}"
            if force:
                range_desc += " (FORCE - will destroy if active)"
            
            if not click.confirm(
                f'Are you sure you want to completely remove {range_desc}?\n'
                'This will delete all files, images, and records permanently.'
            ):
                self.console.print('[yellow]Operation cancelled[/yellow]')
                return True
            
            self.console.print(f"[bold blue]Removing cyber range:[/bold blue] {range_id}")
            
            orchestrator, _ = self.create_orchestrator()
            if not orchestrator:
                return False
            
            # Check if range exists
            range_metadata = orchestrator.get_range(range_id)
            if not range_metadata:
                self.error_display.display_range_not_found(range_id)
                self._check_legacy_ranges(range_id)
                return False
            
            # Show range info before removal
            self._show_removal_info(range_metadata)
            
            # Remove the range
            success = orchestrator.remove_range(range_id, force=force)
            
            if success:
                self.console.print(MessageFormatter.success(
                    f"Cyber range {range_id} removed completely"
                ))
                self.console.print("[dim]All files, images, and records have been deleted[/dim]")
                return True
            else:
                self._handle_removal_failure(range_metadata, force)
                return False
                
        except Exception as e:
            self.handle_error(e, "remove")
            return False
    
    def _get_libvirt_uri(self, range_metadata) -> str:
        """获取libvirt连接URI"""
        libvirt_uri = 'qemu:///system'  # Default
        if (range_metadata.provider_config and 
            'libvirt_uri' in range_metadata.provider_config):
            libvirt_uri = range_metadata.provider_config['libvirt_uri']
            
        if self.verbose:
            self.log_verbose(f"Using libvirt URI: {libvirt_uri}")
            
        return libvirt_uri
    
    def _remove_records(self, orchestrator, range_id: str, force: bool) -> bool:
        """删除靶场记录"""
        self.console.print(f"🗑️  [blue]Removing all records for cyber range {range_id}...[/blue]")
        
        remove_success = orchestrator.remove_range(range_id, force=force)
        if remove_success:
            self.console.print(MessageFormatter.success(
                f"All records for cyber range {range_id} removed completely"
            ))
            return True
        else:
            self.console.print(MessageFormatter.warning(
                f"Failed to remove records for cyber range {range_id}"
            ))
            self.console.print(f"[dim]You can manually run: cyris rm {range_id}[/dim]")
            return False
    
    def _check_legacy_ranges(self, range_id: str) -> None:
        """检查遗留靶场"""
        range_dir = self.config.cyber_range_dir / range_id
        if range_dir.exists():
            self.console.print(f"[yellow]WARNING: Found range directory on filesystem: {range_dir}[/yellow]")
            self.console.print(f"[dim]Use legacy cleanup: main/range_cleanup.sh {range_id} CONFIG[/dim]")
    
    def _show_removal_info(self, range_metadata) -> None:
        """显示删除信息"""
        self.console.print(f"Range: {range_metadata.name}")
        self.console.print(f"Status: {range_metadata.status.value}")
        self.console.print(f"Created: {range_metadata.created_at}")
    
    def _handle_removal_failure(self, range_metadata, force: bool) -> None:
        """处理删除失败"""
        self.console.print(MessageFormatter.error(f"Failed to remove cyber range"))
        
        if not force and range_metadata.status.value != 'destroyed':
            range_id = range_metadata.range_id
            self.console.print(
                f"[dim]Range status is '{range_metadata.status.value}' - "
                f"use --force to remove active ranges[/dim]"
            )
            self.console.print(f"[dim]Or destroy first: cyris destroy {range_id}[/dim]")