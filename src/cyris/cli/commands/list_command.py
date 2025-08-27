"""
List命令处理器
处理靶场列表显示逻辑
"""

from typing import Optional

from .base_command import BaseCommandHandler, ServiceMixin
from cyris.cli.presentation import RangeDisplayManager


class ListCommandHandler(BaseCommandHandler, ServiceMixin):
    """List命令处理器 - 显示靶场列表"""
    
    def __init__(self, config, verbose: bool = False):
        super().__init__(config, verbose)
        self.display_manager = RangeDisplayManager()
    
    def execute(self, range_id: Optional[str] = None, list_all: bool = False, 
                verbose: bool = False) -> bool:
        """执行list命令"""
        try:
            orchestrator, provider = self.create_orchestrator()
            if not orchestrator:
                return False
            
            if range_id:
                return self._show_specific_range(orchestrator, range_id)
            else:
                return self._list_all_ranges(orchestrator, list_all, verbose)
                
        except Exception as e:
            self.handle_error(e, "list")
            return False
    
    def _show_specific_range(self, orchestrator, range_id: str) -> bool:
        """显示特定靶场详情"""
        if not self.validate_range_id(range_id):
            return False
        
        self.console.print(f"[bold blue]Cyber range [bold cyan]{range_id}[/bold cyan] details:[/bold blue]")
        
        range_metadata = orchestrator.get_range(range_id)
        if range_metadata:
            # Display basic info
            self.console.print(f"  Name: [cyan]{range_metadata.name}[/cyan]")
            
            # Use StatusFormatter for status display
            from cyris.cli.presentation import StatusFormatter
            status_text = StatusFormatter.format_status(
                range_metadata.status.value, 
                range_metadata.status.value.upper()
            )
            self.console.print("  Status: ", end="")
            self.console.print(status_text)
            
            self.console.print(f"  Created: [green]{range_metadata.created_at}[/green]")
            self.console.print(f"  Description: {range_metadata.description}")
            
            if range_metadata.tags:
                self.console.print(f"  Tags: [yellow]{range_metadata.tags}[/yellow]")
            
            return True
        else:
            self.error_console.print(f"[bold red]Range {range_id} not found[/bold red]")
            return False
    
    def _list_all_ranges(self, orchestrator, list_all: bool, verbose: bool) -> bool:
        """列出所有靶场"""
        ranges = orchestrator.list_ranges()
        
        if not ranges:
            self.console.print("[yellow]No cyber ranges found in orchestrator[/yellow]")
            # Fallback: Check filesystem for range directories
            self._check_filesystem_ranges()
            return True
        
        # Use display manager for consistent formatting
        self.display_manager.display_range_list(ranges, list_all)
        
        if verbose:
            self._show_verbose_info(orchestrator, ranges)
        
        return True
    
    def _check_filesystem_ranges(self) -> None:
        """检查文件系统中的靶场目录"""
        ranges_dir = self.config.cyber_range_dir
        if ranges_dir.exists():
            range_dirs = [d for d in ranges_dir.iterdir() if d.is_dir()]
            if range_dirs:
                self.console.print(f"Found [cyan]{len(range_dirs)}[/cyan] range directories on filesystem:")
                for range_dir in sorted(range_dirs):
                    self.console.print(f"  [cyan]{range_dir.name}[/cyan] [dim](filesystem only)[/dim]")
        else:
            self.error_console.print(f"[bold red]Cyber range directory does not exist: {ranges_dir}[/bold red]")
    
    def _show_verbose_info(self, orchestrator, ranges) -> None:
        """显示详细信息，包括VM IP地址"""
        for range_meta in ranges:
            if range_meta.status.value in ['active', 'creating']:
                resources = orchestrator.get_range_resources(range_meta.range_id)
                if resources and resources.get('guests'):
                    self.console.print(f"\n[bold cyan]Range {range_meta.range_id} VM Details:[/bold cyan]")
                    
                    # Get libvirt URI from range metadata
                    libvirt_uri = "qemu:///system"
                    if range_meta.provider_config:
                        libvirt_uri = range_meta.provider_config.get('libvirt_uri', libvirt_uri)
                    
                    try:
                        from cyris.tools.vm_ip_manager import VMIPManager
                        ip_manager = VMIPManager(libvirt_uri=libvirt_uri)
                        
                        for guest in resources['guests']:
                            try:
                                health_info = ip_manager.get_vm_health_info(guest)
                                self._display_vm_summary(guest, health_info)
                            except Exception as e:
                                self.console.print(f"  [red]{guest}[/red]: [dim]Status check failed - {str(e)}[/dim]")
                        
                        ip_manager.close()
                        
                    except ImportError:
                        self.console.print("[yellow]  VM details not available (VMIPManager missing)[/yellow]")
                    except Exception as e:
                        self.console.print(f"[red]  Error getting VM details: {str(e)}[/red]")
    
    def _display_vm_summary(self, guest: str, health_info) -> None:
        """显示VM简要信息（用于list -v）"""
        status_icon = ":green_heart:" if getattr(health_info, 'is_healthy', False) else ":cross_mark:"
        libvirt_status = getattr(health_info, 'libvirt_status', 'unknown')
        
        # Get IP addresses
        ip_addresses = getattr(health_info, 'ip_addresses', [])
        if ip_addresses:
            ip_text = f"[green]{', '.join(ip_addresses)}[/green]"
            # Check network reachability
            if hasattr(health_info, 'network_reachable') and health_info.network_reachable:
                network_status = "[green]✓[/green]"
            else:
                network_status = "[yellow]?[/yellow]"
        else:
            ip_text = "[dim]No IP assigned[/dim]"
            network_status = "[dim]-[/dim]"
        
        self.console.print(f"  {status_icon} [cyan]{guest}[/cyan] ({libvirt_status}) - {ip_text} {network_status}")
    
    def _check_running_vms(self, provider) -> None:
        """检查运行中的VM（复用原有逻辑）"""
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
                    self.console.print(f"\n[yellow]Running KVM VMs (potentially orphaned):[/yellow]")
                    for vm in cyris_vms:
                        self.console.print(f"  [red]{vm}[/red] (running but not in orchestrator)")
                    self.console.print(f"  Found {len(cyris_vms)} CyRIS VMs running in KVM")
                    
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # virsh not available
        except Exception as e:
            if self.verbose:
                self.log_verbose(f"Failed to check running VMs: {e}")