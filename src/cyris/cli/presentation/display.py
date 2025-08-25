"""
显示管理器 - 复杂显示逻辑的封装
处理靶场状态、错误信息等复杂显示场景
"""

from typing import Dict, List, Optional, Any
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich.text import Text
from rich.markup import escape

from .formatters import StatusFormatter, MessageFormatter
from .console import get_console, get_error_console


class RangeDisplayManager:
    """靶场显示管理器 - 处理复杂的靶场状态显示"""
    
    def __init__(self):
        self.console = get_console()
        self.error_console = get_error_console()
    
    def display_range_list(self, ranges: List[Any], show_all: bool = False) -> None:
        """显示靶场列表"""
        if not ranges:
            self.console.print(MessageFormatter.info("No cyber ranges found"))
            return
        
        filter_text = "all" if show_all else "active only"
        self.console.print(Text.assemble(
            ("\n", ""),
            ("Cyber Ranges", "bold blue"),
            (" (", "dim"),
            (filter_text, "dim"),
            (")", "dim")
        ))
        
        displayed_count = 0
        for range_meta in sorted(ranges, key=lambda r: r.created_at):
            if not show_all and range_meta.status.value not in ['active', 'creating']:
                continue
            
            displayed_count += 1
            self._display_single_range_summary(range_meta)
        
        if displayed_count == 0:
            self.console.print("  [dim]No ranges match the filter criteria[/dim]")
    
    def display_range_status(self, range_metadata: Any, resources: Optional[Dict] = None, 
                           verbose: bool = False) -> None:
        """显示详细的靶场状态"""
        # Create status table
        table = Table(show_header=False, show_edge=False, padding=(0, 1))
        table.add_column("Field", style="dim", width=15)
        table.add_column("Value")
        
        # Add basic info
        status_text = StatusFormatter.format_status(
            range_metadata.status.value, 
            range_metadata.status.value.upper()
        )
        table.add_row("Status", status_text)
        table.add_row("Name", Text(escape(range_metadata.name), style="bold"))
        table.add_row("Description", escape(range_metadata.description))
        table.add_row("Created", range_metadata.created_at.strftime('%Y-%m-%d %H:%M:%S'))
        table.add_row("Last Modified", range_metadata.last_modified.strftime('%Y-%m-%d %H:%M:%S'))
        
        if range_metadata.owner:
            table.add_row("Owner", escape(range_metadata.owner))
        
        if range_metadata.tags:
            tags_text = self._format_tags(range_metadata.tags)
            table.add_row("Tags", tags_text)
        
        self.console.print(table)
        
        # Show resource information
        if resources:
            self._display_resource_info(resources, verbose)
    
    def display_ssh_info(self, range_metadata: Any, resources: Dict, 
                        ip_manager: Optional[Any] = None) -> None:
        """显示SSH连接信息"""
        self.console.print(Text.assemble(
            ("SSH Connection Information for Range ", "bold blue"),
            (range_metadata.range_id, "bold cyan"),
            (":", "bold blue")
        ))
        
        self.console.print(Text.assemble(
            ("Range Name: ", "dim"),
            (escape(range_metadata.name), "cyan")
        ))
        
        status_text = StatusFormatter.format_status(
            range_metadata.status.value, 
            range_metadata.status.value
        )
        self.console.print(Text.assemble(
            ("Status: ", "dim"),
            status_text
        ))
        
        self.console.print("=" * 60)
        
        # Display SSH info for each VM
        guest_ids = resources.get('guests', [])
        for vm_id in guest_ids:
            self._display_vm_ssh_info(vm_id, ip_manager)
    
    def _display_single_range_summary(self, range_meta: Any) -> None:
        """显示单个靶场的摘要信息"""
        status_text = StatusFormatter.format_status(
            range_meta.status.value, 
            range_meta.status.value.upper()
        )
        
        header = Text.assemble(
            ("  ", ""),
            status_text,
            (" ", ""),
            (str(range_meta.range_id), "bold"),
            (": ", "bold"),
            (escape(range_meta.name), "")
        )
        self.console.print(header)
        
        self.console.print(Text.assemble(
            (" ", ""),
            ("Created:", "dim"),
            (" ", ""),
            (range_meta.created_at.strftime('%Y-%m-%d %H:%M'), "")
        ))
        
        if range_meta.description:
            self.console.print(Text.assemble(
                (" ", ""),
                ("Description:", "dim"),
                (" ", ""),
                (escape(range_meta.description), "")
            ))
    
    def _display_resource_info(self, resources: Dict, verbose: bool) -> None:
        """显示资源信息"""
        self.console.print(f"\n[bold]Resources:[/bold]")
        if resources.get('hosts'):
            self.console.print(f"  Hosts: [green]{len(resources['hosts'])}[/green]")
        if resources.get('guests'):
            self.console.print(f"  Guests: [green]{len(resources['guests'])}[/green]")
            
            if verbose:
                # Show detailed VM health information
                self._display_vm_health_details(resources['guests'])
            else:
                self.console.print(Text("💡 Use --verbose to see detailed VM health status", style="blue"))
    
    def _display_vm_health_details(self, guests: list) -> None:
        """显示VM健康状态详细信息"""
        try:
            # Import VM IP Manager for health checks
            from cyris.tools.vm_ip_manager import VMIPManager
            
            # Default libvirt URI - could be parameterized later
            libvirt_uri = "qemu:///system"
            ip_manager = VMIPManager(libvirt_uri=libvirt_uri)
            
            for guest in guests:
                try:
                    health_info = ip_manager.get_vm_health_info(guest)
                    self._display_single_vm_health(guest, health_info)
                except Exception as e:
                    self.console.print(Text.assemble(
                        (f"[ERROR] Health check for {guest}: ", "bold red"),
                        (str(e), "red")
                    ))
                    
            ip_manager.close()
            
        except ImportError:
            self.console.print("[yellow]⚠️  VM health status checking not available[/yellow]")
        except Exception as e:
            self.console.print(Text.assemble(
                ("[ERROR] Health check system error: ", "bold red"),
                (str(e), "red")
            ))
    
    def _display_single_vm_health(self, vm_id: str, health_info: Any) -> None:
        """显示单个VM的健康信息"""
        from rich.table import Table
        from rich.panel import Panel
        
        # Create VM info table
        vm_table = Table(show_header=False, show_edge=False, padding=(0, 1), width=80)
        vm_table.add_column("Field", style="dim", width=12)
        vm_table.add_column("Value")
        
        # Add VM information
        if hasattr(health_info, 'ip_addresses') and health_info.ip_addresses:
            for ip in health_info.ip_addresses:
                vm_table.add_row("IP Address", Text(ip, style="green"))
        else:
            vm_table.add_row("IP Address", Text("Not available", style="yellow"))
        
        if hasattr(health_info, 'status'):
            vm_table.add_row("VM Status", Text(health_info.status, style="cyan"))
        
        if hasattr(health_info, 'disk_path') and health_info.disk_path:
            vm_table.add_row("Disk", Text(health_info.disk_path, style="dim"))
        
        # Create status icon
        is_healthy = hasattr(health_info, 'is_healthy') and health_info.is_healthy
        status_icon = ":green_heart:" if is_healthy else ":cross_mark:"
        status_color = "green" if is_healthy else "red"
        
        panel_title = Text.assemble(
            (status_icon, status_color),
            (" ", ""),
            (vm_id, "bold")
        )
        
        # Create panel with VM information
        vm_panel = Panel(vm_table, title=panel_title, expand=False)
        self.console.print(vm_panel)
    
    def _display_vm_ssh_info(self, vm_id: str, ip_manager: Optional[Any]) -> None:
        """显示单个VM的SSH信息"""
        self.console.print(Text.assemble(
            ("\nVM: ", "bold magenta"),
            (vm_id, "cyan")
        ))
        
        if ip_manager:
            try:
                health_info = ip_manager.get_vm_health_info(vm_id)
                self._display_vm_health_status(health_info)
            except Exception as e:
                self.error_console.print(Text.assemble(
                    ("   [ERROR] Health check failed: ", "bold red"),
                    (str(e), "red")
                ))
        else:
            self.console.print("   [yellow]⚠️  VM status checking not available[/yellow]")
    
    def _display_vm_health_status(self, health_info: Any) -> None:
        """显示VM健康状态"""
        status_text = StatusFormatter.format_status(
            'ok' if health_info.is_healthy else 'error', 'Status'
        )
        
        self.console.print(Text.assemble(
            ("   ", ""),
            status_text,
            (": ", ""),
            (health_info.libvirt_status, "cyan"),
            (" → ", "dim"),
            ("healthy" if health_info.is_healthy else "unhealthy", 
             "green" if health_info.is_healthy else "red")
        ))
        
        if health_info.ip_addresses:
            self._display_vm_network_info(health_info)
    
    def _display_vm_network_info(self, health_info: Any) -> None:
        """显示VM网络信息"""
        ip_parts = [("   IP: IP Addresses: ", "blue")]
        for i, ip in enumerate(health_info.ip_addresses):
            if i > 0:
                ip_parts.append((", ", "dim"))
            ip_parts.append((ip, "green"))
        ip_text = Text.assemble(*ip_parts)
        self.console.print(ip_text)
        
        if health_info.network_reachable:
            self.console.print(Text("   NET: Network: Reachable [OK]", style="green"))
        else:
            self.console.print(Text("   NET: Network: Not reachable WARNING:", style="yellow"))
    
    def _format_tags(self, tags: Dict) -> Text:
        """格式化标签显示"""
        tags_text = Text()
        for i, (k, v) in enumerate(tags.items()):
            if i > 0:
                tags_text.append(", ")
            tags_text.append(escape(k), style="cyan")
            tags_text.append("=")
            tags_text.append(escape(str(v)))
        return tags_text


class ErrorDisplayManager:
    """错误显示管理器 - 统一的错误处理和显示"""
    
    def __init__(self):
        self.error_console = get_error_console()
    
    def display_error(self, message: str, details: Optional[str] = None) -> None:
        """显示错误信息"""
        self.error_console.print(MessageFormatter.error(message))
        if details:
            self.error_console.print(f"  Details: {details}")
    
    def display_validation_errors(self, errors: List[str]) -> None:
        """显示验证错误列表"""
        self.error_console.print(MessageFormatter.error("Validation failed:"))
        for i, error in enumerate(errors, 1):
            self.error_console.print(f"  {i}. {error}")
    
    def display_command_error(self, command: str, error: Exception) -> None:
        """显示命令执行错误"""
        self.error_console.print(MessageFormatter.error(f"Command '{command}' failed"))
        self.error_console.print(f"  Error: {str(error)}")
    
    def display_configuration_error(self, config_path: str, error: str) -> None:
        """显示配置错误"""
        self.error_console.print(MessageFormatter.error(f"Configuration error in {config_path}"))
        self.error_console.print(f"  {error}")
    
    def display_range_not_found(self, range_id: str) -> None:
        """显示靶场未找到错误"""
        self.error_console.print(Text.assemble(
            ("[ERROR] Range ", "bold red"),
            (range_id, "red"),
            (" not found", "bold red")
        ))