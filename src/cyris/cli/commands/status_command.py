"""
Status命令处理器
处理靶场状态查看逻辑 - 完整实现原始功能
"""

import sys
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich.text import Text
from rich.markup import escape

from .base_command import BaseCommandHandler, ServiceMixin


class StatusCommandHandler(BaseCommandHandler, ServiceMixin):
    """Status命令处理器 - 显示靶场状态"""
    
    def execute(self, range_id: str, verbose: bool = False) -> bool:
        """执行status命令"""
        try:
            if not self.validate_range_id(range_id):
                return False
            
            self.console.print(f"\n[bold blue]Cyber Range Status[/bold blue]: [bold]{range_id}[/bold]")
            
            orchestrator, provider = self.create_orchestrator()
            if not orchestrator:
                return False
            
            # Check orchestrator first
            range_metadata = orchestrator.get_range(range_id)
            
            if range_metadata:
                # Display basic range information
                self._display_range_info(range_metadata)
                
                # Get and display resource information with verbose details
                resources = orchestrator.get_range_resources(range_id)
                if resources:
                    self._display_resources_info(resources, range_metadata, verbose)
                
                # Check filesystem status
                self._check_filesystem_status(range_id, range_metadata, verbose)
                
                return True
            else:
                self.error_console.print(Text("  [ERROR] Range not found in orchestrator", style="bold red"))
                self._check_filesystem_status(range_id, None, verbose)
                return False
                
        except Exception as e:
            self.error_console.print(Text.assemble(
                ("[ERROR] Error checking range status: ", "bold red"),
                (str(e), "red")
            ))
            if verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _display_range_info(self, range_metadata) -> None:
        """显示基本靶场信息"""
        # Create a beautiful info table using Rich
        table = Table(show_header=False, show_edge=False, padding=(0, 1))
        table.add_column("Field", style="dim", width=15)
        table.add_column("Value")

        # Add status with proper Rich Text object
        status_text = self._get_status_text(range_metadata.status.value, range_metadata.status.value.upper())
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

        self.console.print(table)
    
    def _get_status_text(self, status: str, label: str = None) -> Text:
        """Get Rich Text object with appropriate styling for status"""
        status_lower = status.lower()
        label_text = escape(label or status)
        
        # Use Rich emoji names and proper styling
        styles = {
            'active': (':green_circle:', 'green'),
            'creating': (':construction:', 'yellow'),
            'destroying': (':bomb:', 'red'),
            'destroyed': (':skull:', 'red'),
            'error': (':cross_mark:', 'red'),
            'stopped': (':stop_button:', 'red'),
            'healthy': (':green_heart:', 'green'),
            'unhealthy': (':cross_mark:', 'red')
        }
        
        if status_lower in styles:
            emoji, color = styles[status_lower]
            return Text.assemble(
                (emoji, color),
                (" ", ""),
                (label_text, color)
            )
        else:
            return Text(label_text, style="white")
    
    def _display_resources_info(self, resources, range_metadata, verbose: bool) -> None:
        """显示资源信息"""
        self.console.print(f"\n[bold]Resources:[/bold]")
        if resources.get('hosts'):
            self.console.print(f"  Hosts: [green]{len(resources['hosts'])}[/green]")
        if resources.get('guests'):
            self.console.print(f"  Guests: [green]{len(resources['guests'])}[/green]")

            # Show VM health information using Rich Panel
            if resources.get('guests') and verbose:
                # Get libvirt URI from range metadata
                libvirt_uri = "qemu:///system"
                if range_metadata.provider_config:
                    libvirt_uri = range_metadata.provider_config.get('libvirt_uri', libvirt_uri)

                try:
                    from cyris.tools.vm_ip_manager import VMIPManager
                    ip_manager = VMIPManager(libvirt_uri=libvirt_uri)

                    for guest in resources['guests']:
                        try:
                            health_info = ip_manager.get_vm_health_info(guest)
                            self._display_vm_health_panel(guest, health_info)
                        except Exception as e:
                            # Use escape to prevent Rich markup errors and show basic VM info
                            self._display_vm_error_panel(guest, str(e))

                    ip_manager.close()

                except ImportError:
                    self.console.print(Text("WARNING: VM health checking not available", style="yellow"))
                except Exception as e:
                    self.error_console.print(Text.assemble(
                        ("[ERROR] Health check error: ", "bold red"),
                        (str(e), "red")
                    ))

            elif resources.get('guests'):
                self.console.print(Text("💡 Use --verbose to see detailed VM health status", style="blue"))
    
    def _display_vm_health_panel(self, guest: str, health_info) -> None:
        """显示单个VM的健康状态面板"""
        # Create VM info table using Rich best practices
        vm_table = Table(show_header=False, show_edge=False, padding=(0, 1), width=80)
        vm_table.add_column("Field", style="dim", width=12)
        vm_table.add_column("Value")

        # Use Text.assemble for complex content
        if hasattr(health_info, 'libvirt_status') and health_info.libvirt_status:
            libvirt_text = Text(escape(str(health_info.libvirt_status)), style="cyan")
            vm_table.add_row("Libvirt", libvirt_text)

        if hasattr(health_info, 'is_healthy'):
            healthy_text = Text("Yes", style="green") if health_info.is_healthy else Text("No", style="red")
            vm_table.add_row("Healthy", healthy_text)

        if hasattr(health_info, 'ip_addresses') and health_info.ip_addresses:
            # Use Text.assemble for IP addresses properly
            ip_parts = []
            for i, ip in enumerate(health_info.ip_addresses):
                if i > 0:
                    ip_parts.append((", ", "dim"))
                ip_parts.append((ip, "green"))
            ip_text = Text.assemble(*ip_parts)
            vm_table.add_row("IP Address", ip_text)

            if hasattr(health_info, 'network_reachable'):
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

        if hasattr(health_info, 'uptime') and health_info.uptime:
            vm_table.add_row("Uptime", Text(escape(str(health_info.uptime)), style="white"))

        if hasattr(health_info, 'disk_path') and health_info.disk_path:
            vm_table.add_row("Disk", Text(escape(health_info.disk_path), style="dim"))

        # Create VM Panel with status indicator using Rich Text.assemble
        is_healthy = hasattr(health_info, 'is_healthy') and health_info.is_healthy
        vm_status_icon = ":green_heart:" if is_healthy else ":cross_mark:"
        panel_title_text = Text.assemble(
            (vm_status_icon, "green" if is_healthy else "red"),
            (" ", ""),
            (escape(guest), "bold")
        )

        # Create error details if any
        panel_content = [vm_table]
        if hasattr(health_info, 'error_details') and health_info.error_details:
            # Create error details table with automatic text wrapping
            error_table = Table(show_header=False, show_edge=False, padding=(0, 0, 0, 1))
            error_table.add_column("", style="red", width=3, no_wrap=True)
            error_table.add_column("Error Details", overflow="fold")

            error_table.add_row("", Text("Error Details:", style="bold red"))

            for i, error in enumerate(health_info.error_details, 1):
                error_table.add_row(f"{i}.", Text(escape(str(error)), style="red"))

            panel_content.append(error_table)

        # Create Panel for this VM with auto-wrapping support
        vm_panel = Panel(
            Group(*panel_content),
            title=panel_title_text,
            expand=False,
            border_style="red" if not is_healthy else "green"
        )
        self.console.print(vm_panel)
    
    def _display_vm_error_panel(self, guest: str, error_msg: str) -> None:
        """显示VM错误信息面板"""
        # Create simple error table
        error_table = Table(show_header=False, show_edge=False, padding=(0, 1))
        error_table.add_column("Field", style="dim", width=12)
        error_table.add_column("Value")
        
        error_table.add_row("Status", Text("Health check failed", style="red"))
        error_table.add_row("Error", Text(escape(error_msg), style="red"))
        
        # Create error panel
        panel_title_text = Text.assemble(
            (":cross_mark:", "red"),
            (" ", ""),
            (escape(guest), "bold")
        )
        
        error_panel = Panel(
            error_table,
            title=panel_title_text,
            expand=False,
            border_style="red"
        )
        self.console.print(error_panel)
    
    def _check_filesystem_status(self, range_id: str, range_metadata, verbose: bool) -> None:
        """检查文件系统状态"""
        self.console.print()  # Empty line for spacing
        
        range_dir = self.config.cyber_range_dir / range_id
        
        if range_dir.exists():
            # Simple directory display following Rich best practices
            self.console.print(Text.assemble(
                ("Directory:", "dim"),
                (" ", ""),
                (str(range_dir), "cyan")
            ))
            
            # Show directory contents if verbose - simplified display
            if verbose:
                self._show_directory_contents_verbose(range_dir)
        else:
            if not range_metadata:
                self.error_console.print(Text.assemble(
                    ("  [ERROR] Range ", "bold red"),
                    (range_id, "bold red"),
                    (" not found (no orchestrator record, no filesystem directory)", "bold red")
                ))
                sys.exit(1)
            else:
                self.console.print(Text("  WARNING: Range exists in orchestrator but no filesystem directory found", style="yellow"))
    
    def _show_directory_contents_verbose(self, range_dir) -> None:
        """显示目录内容（verbose模式）"""
        try:
            contents = []
            for item in range_dir.iterdir():
                contents.append(item)

            if contents:
                self.console.print(Text.assemble(
                    ("Contents (", "dim"),
                    (str(len(contents)), "cyan"),
                    (" items):", "dim")
                ))
                for item in sorted(contents):
                    icon = "📁" if item.is_dir() else "📄"
                    style = "yellow" if item.is_dir() else "white"
                    self.console.print(Text.assemble(
                        ("  ", ""),
                        (icon, style),
                        (" ", ""),
                        (item.name, style)
                    ))
            else:
                self.console.print(Text("  (empty directory)", style="dim italic"))

        except Exception as e:
            self.error_console.print(Text.assemble(
                ("Could not list directory contents: ", "red"),
                (str(e), "red")
            ))