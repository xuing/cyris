"""
Status Command Handler
Handles cyber range status checking logic with comprehensive status display
"""

import sys
from typing import List, Dict, Any
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich.text import Text
from rich.markup import escape

from .base_command import BaseCommandHandler
from ..diagnostic_messages import DiagnosticMessageFormatter
from ...tools.vm_diagnostics import quick_vm_health_check


class StatusCommandHandler(BaseCommandHandler):
    """Status command handler - Display cyber range status with detailed VM information"""
    
    def execute(self, range_id: str, verbose: bool = False) -> bool:
        """Execute status command with comprehensive range status display"""
        try:
            if not self.validate_range_id(range_id):
                return False
            
            self.console.print(f"\n[bold blue]Cyber Range Status[/bold blue]: [bold]{range_id}[/bold]")
            
            orchestrator, provider, singleton = self.create_orchestrator()
            if not orchestrator:
                return False
            
            with singleton:
            
                # Get detailed status using our enhanced method
                detailed_status = orchestrator.get_range_status_detailed(range_id)
                
                if detailed_status:
                    # Display comprehensive range status
                    self._display_detailed_status(detailed_status, verbose)
                    return True
                else:
                    # Fallback to basic range check
                    range_metadata = orchestrator.get_range(range_id) if hasattr(orchestrator, 'get_range') else None
                    
                    if range_metadata:
                        self.console.print("[yellow]⚠️ Range exists but detailed status unavailable[/yellow]")
                        self._display_basic_range_info(range_metadata)
                        return True
                    else:
                        self.error_console.print(Text("  [ERROR] Range not found", style="bold red"))
                        # Check filesystem status
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
    
    def _display_detailed_status(self, detailed_status: Dict[str, Any], verbose: bool) -> None:
        """Display comprehensive range status with VM information"""
        
        # Basic range information
        self.console.print("\n[bold blue]Range Overview[/bold blue]")
        
        # Create overview table
        overview_table = Table(show_header=False, show_edge=False, padding=(0, 1))
        overview_table.add_column("Field", style="dim", width=15)
        overview_table.add_column("Value")
        
        # Status with proper styling
        status_text = self._get_status_text(detailed_status['status'], detailed_status['status'].upper())
        overview_table.add_row("Status", status_text)
        overview_table.add_row("Name", Text(escape(detailed_status['name']), style="bold cyan"))
        overview_table.add_row("Description", escape(detailed_status['description']))
        overview_table.add_row("Created", detailed_status['created_at'][:19].replace('T', ' '))
        overview_table.add_row("VMs", Text(str(detailed_status['vm_count']), style="green"))
        overview_table.add_row("Provider", Text(detailed_status['provider'].upper(), style="cyan"))
        
        self.console.print(overview_table)
        
        # VM Status Information
        vms = detailed_status.get('vms', [])
        if vms:
            self.console.print(f"\n[bold blue]Virtual Machines ({len(vms)})[/bold blue]")
            self._display_vm_status_table(vms, verbose)
        
        # Topology information if available and verbose
        if verbose and detailed_status.get('topology_metadata'):
            self._display_topology_info(detailed_status['topology_metadata'])
    
    def _display_vm_status_table(self, vms: List[Dict[str, Any]], verbose: bool) -> None:
        """Display VM status in a formatted table"""
        # Create VM status table
        vm_table = Table(show_header=True, show_edge=True, padding=(0, 1))
        vm_table.add_column("VM Name", style="cyan", width=20)
        vm_table.add_column("Status", width=12)
        vm_table.add_column("IP Address", style="green", width=15)
        vm_table.add_column("SSH", width=8)
        if verbose:
            vm_table.add_column("Last Check", style="dim", width=16)
        
        for vm in vms:
            # Status with emoji
            vm_status = vm.get('status', 'unknown')
            if vm_status == 'running':
                status_display = Text.assemble(
                    (":green_circle: ", "green"),
                    ("Running", "green")
                )
            elif vm_status == 'shutoff':
                status_display = Text.assemble(
                    (":red_circle: ", "red"),
                    ("Stopped", "red")
                )
            elif vm_status == 'error':
                status_display = Text.assemble(
                    (":cross_mark: ", "red"),
                    ("Error", "red")
                )
            else:
                status_display = Text(vm_status.capitalize(), style="yellow")
            
            # IP Address with error details
            ip_addr = vm.get('ip', 'N/A')
            if ip_addr and ip_addr != 'N/A':
                ip_display = Text(ip_addr, style="green")
            else:
                ip_display = Text("N/A", style="dim")
                # Show error details if available
                error_details = vm.get('error_details')
                if error_details and verbose:
                    ip_display = Text(f"N/A ({error_details})", style="dim")
            
            # SSH Status
            ssh_accessible = vm.get('ssh_accessible', False)
            ssh_display = Text.assemble(
                (":check_mark: ", "green"),
                ("Yes", "green")
            ) if ssh_accessible else Text.assemble(
                (":cross_mark: ", "red"),
                ("No", "red")
            )
            
            # Build row data
            row_data = [
                Text(escape(vm['name']), style="bold"),
                status_display,
                ip_display,
                ssh_display
            ]
            
            if verbose:
                last_check = vm.get('last_checked', '')
                if last_check:
                    # Format timestamp nicely
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%H:%M:%S')
                        row_data.append(Text(formatted_time, style="dim"))
                    except:
                        row_data.append(Text("--:--:--", style="dim"))
                else:
                    row_data.append(Text("--:--:--", style="dim"))
            
            vm_table.add_row(*row_data)
            
            # Show error details if any
            if verbose and vm.get('error'):
                error_text = Text(f"Error: {vm['error']}", style="red")
                if verbose:
                    vm_table.add_row("", error_text, "", "", "" if verbose else "")
        
        self.console.print(vm_table)
        
        # Display error details for VMs without IPs (if verbose or any errors)
        vms_with_errors = [vm for vm in vms if not vm.get('ip') and vm.get('error_details')]
        if vms_with_errors:
            self.console.print("\n[bold yellow]IP Discovery Details:[/bold yellow]")
            for vm in vms_with_errors:
                vm_name = vm['name']
                error_details = vm.get('error_details', 'No details available')
                self.console.print(f"  • [cyan]{vm_name}[/cyan]: {error_details}", style="dim")
        
        # Summary information
        running_count = sum(1 for vm in vms if vm.get('status') == 'running')
        ssh_count = sum(1 for vm in vms if vm.get('ssh_accessible', False))
        
        summary_parts = []
        if running_count > 0:
            summary_parts.append(f"[green]{running_count} running[/green]")
        if ssh_count > 0:
            summary_parts.append(f"[green]{ssh_count} SSH accessible[/green]")
        
        if summary_parts:
            self.console.print(f"\n[dim]Summary: {', '.join(summary_parts)}[/dim]")
        
        # Smart diagnostics - run health checks on problematic VMs
        self._run_smart_diagnostics(vms, verbose)
    
    def _display_topology_info(self, topology_metadata: Dict[str, Any]) -> None:
        """Display network topology information in verbose mode"""
        if not topology_metadata:
            return
            
        self.console.print(f"\n[bold blue]Network Topology[/bold blue]")
        
        # IP assignments
        ip_assignments = topology_metadata.get('ip_assignments', {})
        if ip_assignments:
            topology_table = Table(show_header=True, show_edge=False, padding=(0, 1))
            topology_table.add_column("VM", style="cyan")
            topology_table.add_column("Assigned IP", style="green")
            topology_table.add_column("Status", style="dim")
            
            for vm_name, assigned_ip in ip_assignments.items():
                topology_table.add_row(
                    escape(vm_name), 
                    assigned_ip,
                    "Configured"
                )
            
            self.console.print(topology_table)
        
        # Network information
        networks = topology_metadata.get('networks', [])
        if networks:
            self.console.print(f"\n[dim]Networks: {len(networks)} configured[/dim]")
    
    def _display_basic_range_info(self, range_metadata) -> None:
        """Display basic range information when detailed status unavailable"""
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
    
    def _check_filesystem_status(self, range_id: str, range_metadata, verbose: bool) -> None:
        """Check filesystem status for range directory and contents"""
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
        """Show directory contents in verbose mode"""
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
    
    def _run_smart_diagnostics(self, vms: List[Dict[str, Any]], verbose: bool) -> None:
        """Run smart diagnostics on VMs with issues"""
        formatter = DiagnosticMessageFormatter(self.console)
        
        # Identify VMs that need diagnostics
        problematic_vms = []
        for vm in vms:
            vm_name = vm.get('name', '')
            
            # Check for common issues that warrant diagnostics
            needs_diagnostics = (
                not vm.get('ip') or                           # No IP address
                vm.get('status') == 'error' or                # Error status  
                not vm.get('ssh_accessible', False) or        # SSH not accessible
                vm.get('error_details')                       # Has error details
            )
            
            if needs_diagnostics:
                problematic_vms.append(vm_name)
        
        if not problematic_vms:
            return
        
        # Run diagnostics on problematic VMs
        self.console.print("\n[bold blue]🔍 Smart Diagnostics[/bold blue]")
        
        for vm_name in problematic_vms:
            try:
                # Run quick health check
                diagnostic_results = quick_vm_health_check(vm_name)
                
                if not diagnostic_results:
                    continue
                
                # Show summary for all VMs, details only in verbose mode
                summary = formatter.format_diagnostic_summary(vm_name, diagnostic_results)
                self.console.print(f"  • [cyan]{vm_name}[/cyan]: {summary}")
                
                # Show detailed diagnostics in verbose mode
                if verbose:
                    details = formatter.format_diagnostic_details(vm_name, diagnostic_results)
                    for detail in details:
                        self.console.print(detail)
                
                # Show quick fixes for critical issues (always show these)
                quick_fixes = formatter.format_quick_fix_suggestions(diagnostic_results)
                if quick_fixes:
                    for fix in quick_fixes[:2]:  # Limit to 2 most important fixes
                        self.console.print(f"    {fix}")
                        
            except Exception as e:
                self.console.print(f"  • [cyan]{vm_name}[/cyan]: [red]Diagnostics failed: {str(e)}[/red]")
        
        if not verbose and problematic_vms:
            self.console.print(f"[dim]\n💡 Tip: Use --verbose flag for detailed diagnostic information[/dim]")