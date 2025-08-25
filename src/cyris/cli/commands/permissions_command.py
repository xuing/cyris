"""
权限设置命令处理器
处理libvirt权限配置逻辑
"""

import os
import subprocess
from pathlib import Path

from .base_command import BaseCommandHandler
from cyris.cli.presentation import MessageFormatter


class PermissionsCommandHandler(BaseCommandHandler):
    """权限设置命令处理器 - 配置libvirt权限"""
    
    def execute(self, dry_run: bool = False) -> bool:
        """执行setup-permissions命令"""
        try:
            self.console.print("[bold blue]Setting up libvirt permissions for CyRIS environment[/bold blue]")
            
            if dry_run:
                self.console.print("[yellow]Dry run mode - showing what would be done[/yellow]")
            
            success = True
            
            # Check and setup directory permissions
            success &= self._setup_directory_permissions(dry_run)
            
            # Check libvirt group membership
            success &= self._check_libvirt_group(dry_run)
            
            # Check QEMU configuration
            success &= self._check_qemu_config(dry_run)
            
            # Check KVM access
            success &= self._check_kvm_access(dry_run)
            
            if success:
                if not dry_run:
                    self.console.print(MessageFormatter.success(
                        "Libvirt permissions setup completed successfully"
                    ))
                else:
                    self.console.print("[green]All permission checks would pass[/green]")
            else:
                self.console.print(MessageFormatter.warning(
                    "Some permission issues were detected - see output above"
                ))
            
            return success
            
        except Exception as e:
            self.handle_error(e, "setup-permissions")
            return False
    
    def _setup_directory_permissions(self, dry_run: bool) -> bool:
        """设置目录权限"""
        self.console.print("\n[bold]📁 Directory Permissions[/bold]")
        
        success = True
        cyber_range_dir = self.config.cyber_range_dir
        
        # Check if cyber range directory exists
        if not cyber_range_dir.exists():
            self.console.print(f"[yellow]Creating cyber range directory: {cyber_range_dir}[/yellow]")
            if not dry_run:
                try:
                    cyber_range_dir.mkdir(parents=True, exist_ok=True)
                    self.console.print(f"[green]✓[/green] Created directory")
                except Exception as e:
                    self.console.print(f"[red]✗[/red] Failed to create directory: {e}")
                    success = False
        else:
            self.console.print(f"[green]✓[/green] Directory exists: {cyber_range_dir}")
        
        # Check directory permissions
        if cyber_range_dir.exists():
            try:
                stat_info = cyber_range_dir.stat()
                current_mode = oct(stat_info.st_mode)[-3:]
                
                if current_mode == '755':
                    self.console.print(f"[green]✓[/green] Directory permissions OK: {current_mode}")
                else:
                    self.console.print(f"[yellow]⚠[/yellow] Directory permissions: {current_mode} (should be 755)")
                    if not dry_run:
                        try:
                            cyber_range_dir.chmod(0o755)
                            self.console.print("[green]✓[/green] Fixed directory permissions")
                        except Exception as e:
                            self.console.print(f"[red]✗[/red] Failed to fix permissions: {e}")
                            success = False
                    else:
                        self.console.print("[dim]Would run: chmod 755 {cyber_range_dir}[/dim]")
                        
            except Exception as e:
                self.console.print(f"[red]✗[/red] Could not check directory permissions: {e}")
                success = False
        
        return success
    
    def _check_libvirt_group(self, dry_run: bool) -> bool:
        """检查libvirt组成员身份"""
        self.console.print("\n[bold]👥 Libvirt Group Membership[/bold]")
        
        try:
            # Check if user is in libvirt group
            result = subprocess.run(['groups'], capture_output=True, text=True, check=True)
            groups = result.stdout.strip().split()
            
            if 'libvirt' in groups:
                self.console.print("[green]✓[/green] User is in libvirt group")
                return True
            else:
                self.console.print("[yellow]⚠[/yellow] User is not in libvirt group")
                self.console.print("[dim]Run: sudo usermod -a -G libvirt $(whoami)[/dim]")
                self.console.print("[dim]Then log out and back in to apply changes[/dim]")
                return False
                
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]✗[/red] Failed to check group membership: {e}")
            return False
        except Exception as e:
            self.console.print(f"[red]✗[/red] Error checking groups: {e}")
            return False
    
    def _check_qemu_config(self, dry_run: bool) -> bool:
        """检查QEMU配置"""
        self.console.print("\n[bold]⚙️  QEMU Configuration[/bold]")
        
        qemu_conf_path = Path('/etc/libvirt/qemu.conf')
        if not qemu_conf_path.exists():
            self.console.print("[yellow]⚠[/yellow] QEMU config file not found")
            return False
        
        try:
            with open(qemu_conf_path) as f:
                content = f.read()
            
            # Check for important settings
            checks = [
                ('user = "root"', "QEMU user configuration"),
                ('group = "root"', "QEMU group configuration"),
                ('dynamic_ownership = 1', "Dynamic ownership"),
            ]
            
            all_good = True
            for pattern, desc in checks:
                if pattern in content and not content.count(f'#{pattern}'):
                    self.console.print(f"[green]✓[/green] {desc} OK")
                else:
                    self.console.print(f"[yellow]?[/yellow] {desc} not explicitly set (using defaults)")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]✗[/red] Could not check QEMU config: {e}")
            return False
    
    def _check_kvm_access(self, dry_run: bool) -> bool:
        """检查KVM访问权限"""
        self.console.print("\n[bold]🖥️  KVM Access[/bold]")
        
        kvm_device = Path('/dev/kvm')
        if not kvm_device.exists():
            self.console.print("[red]✗[/red] /dev/kvm does not exist - KVM not available")
            return False
        
        try:
            # Check if device is accessible
            if os.access(kvm_device, os.R_OK | os.W_OK):
                self.console.print("[green]✓[/green] KVM device accessible")
            else:
                self.console.print("[yellow]⚠[/yellow] KVM device not accessible")
                self.console.print("[dim]User may need to be in kvm group[/dim]")
        
            # Check if libvirtd is running
            result = subprocess.run(['systemctl', 'is-active', 'libvirtd'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.console.print("[green]✓[/green] libvirtd service is active")
                return True
            else:
                self.console.print("[yellow]⚠[/yellow] libvirtd service is not active")
                self.console.print("[dim]Run: sudo systemctl start libvirtd[/dim]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]✗[/red] Error checking KVM access: {e}")
            return False