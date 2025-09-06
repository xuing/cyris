"""
SSH Info Command Handler
Handles SSH connection information display logic
"""

from .base_command import BaseCommandHandler
from cyris.cli.presentation import MessageFormatter


class SSHInfoCommandHandler(BaseCommandHandler):
    """SSH info command handler - Display SSH connection information for ranges"""
    
    def execute(self, range_id: str) -> bool:
        """Execute ssh-info command to display connection details"""
        try:
            if not self.validate_range_id(range_id):
                return False
            
            self.console.print(f"[bold blue]SSH Connection Information[/bold blue]: [cyan]{range_id}[/cyan]")
            
            orchestrator, provider, singleton = self.create_orchestrator()
            if not orchestrator:
                return False
                
            with singleton:
                # Get range metadata
                range_metadata = orchestrator.get_range(range_id)
                if not range_metadata:
                    self.error_display.display_range_not_found(range_id)
                    return False
                
                # Get resources
                resources = orchestrator.get_range_resources(range_id)
                if not resources or not resources.get('guests'):
                    self.console.print("[yellow]No VMs found in this range[/yellow]")
                    return True
                
                # Display SSH info for each VM
                self._display_vm_ssh_info(resources['guests'], provider)
                
                # Show helpful tips
                self._show_ssh_tips()
                
                return True
            
        except Exception as e:
            self.handle_error(e, "ssh-info")
            return False
    
    def _display_vm_ssh_info(self, vms, provider) -> None:
        """显示VM的SSH信息"""
        for i, vm in enumerate(vms, 1):
            # vms is a list of VM ID strings, not dictionaries
            if isinstance(vm, dict):
                vm_id = vm.get('id', f'vm-{i}')
                vm_name = vm.get('name', vm_id)
            else:
                # VM is a string ID
                vm_id = vm
                vm_name = vm_id
            
            self.console.print(f"\n[bold cyan]VM {i}: {vm_name}[/bold cyan]")
            
            # Get IP addresses from provider
            vm_ip = None
            try:
                if hasattr(provider, 'get_vm_ip'):
                    vm_ip = provider.get_vm_ip(vm_id)
            except Exception as e:
                if self.verbose:
                    self.log_verbose(f"Could not get IP for {vm_id}: {e}")
            
            if vm_ip:
                self.console.print(f"   🌐 IP Address: [green]{vm_ip}[/green]")
                self.console.print(f"   🔐 SSH Command: [yellow]ssh user@{vm_ip}[/yellow]")
            else:
                self.console.print("   🌐 IP Address: [dim]Not available (DHCP or not started)[/dim]")
            
            # Get SSH info from provider
            try:
                ssh_info_data = provider.get_vm_ssh_info(vm_id) if hasattr(provider, 'get_vm_ssh_info') else None
                if ssh_info_data:
                    self._display_provider_ssh_info(ssh_info_data, vm_ip is None)
            except Exception as e:
                if self.verbose:
                    self.log_verbose(f"Could not get SSH info for {vm_id}: {e}")
    
    def _display_provider_ssh_info(self, ssh_info_data, show_discovery_commands: bool) -> None:
        """显示提供商的SSH信息"""
        connection_type = ssh_info_data.get('connection_type', 'unknown')
        self.console.print(f"   🔗 Connection Type: [cyan]{connection_type}[/cyan]")
        
        if connection_type == 'bridge':
            network = ssh_info_data.get('network', 'unknown')
            mac_address = ssh_info_data.get('mac_address', 'unknown')
            ssh_port = ssh_info_data.get('ssh_port', 22)
            
            self.console.print(f"   🏠 Network: [cyan]{network}[/cyan]")
            self.console.print(f"   🔗 MAC Address: [dim]{mac_address}[/dim]")
            self.console.print(f"   🚪 SSH Port: [cyan]{ssh_port}[/cyan]")
            
            if show_discovery_commands and 'suggested_commands' in ssh_info_data:
                self.console.print("   📋 [yellow]Manual IP discovery commands:[/yellow]")
                for cmd in ssh_info_data['suggested_commands']:
                    self.console.print(f"      [dim]{cmd}[/dim]")
        
        elif connection_type == 'user_mode':
            if ssh_info_data.get('notes'):
                self.console.print(f"   📝 Notes: [dim]{ssh_info_data['notes']}[/dim]")
            if ssh_info_data.get('alternative'):
                self.console.print(f"   🔄 Alternative: [yellow]{ssh_info_data['alternative']}[/yellow]")
        
        if ssh_info_data.get('notes'):
            self.console.print(f"   📝 Notes: [dim]{ssh_info_data['notes']}[/dim]")
    
    def _show_ssh_tips(self) -> None:
        """显示SSH提示信息"""
        self.console.print("\n[bold blue]💡 SSH Tips:[/bold blue]")
        self.console.print("   • For bridge networking, VMs get DHCP IP addresses")
        self.console.print("   • Use 'nmap -sP 192.168.122.0/24' to scan for active IPs")
        self.console.print("   • VNC console is available on all VMs for direct access")
        self.console.print("   • Default SSH credentials may vary by VM template")