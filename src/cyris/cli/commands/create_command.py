"""
Create命令处理器
处理靶场创建逻辑
"""

from pathlib import Path
from typing import Optional

from .base_command import BaseCommandHandler, ValidationMixin
from cyris.cli.presentation import MessageFormatter


class CreateCommandHandler(BaseCommandHandler, ValidationMixin):
    """Create命令处理器 - 创建新的靶场"""
    
    def execute(self, description_file: Path, range_id: Optional[int] = None,
                dry_run: bool = False, network_mode: str = 'bridge',
                enable_ssh: bool = True) -> bool:
        """执行create命令"""
        try:
            # Validate inputs
            if not self.validate_file_exists(description_file):
                return False
            
            if not self.validate_yaml_file(description_file):
                return False
            
            if not self.validate_network_mode(network_mode):
                return False
            
            # Display creation info
            self.console.print(f"[bold blue]Creating cyber range:[/bold blue] [cyan]{description_file}[/cyan]")
            
            if self.verbose:
                self.log_verbose(f"Configuration: {self.config}")
                self.log_verbose(f"Range ID: {range_id or 'auto-assigned'}")
                self.log_verbose(f"Network mode: {network_mode}")
                self.log_verbose(f"SSH enabled: {enable_ssh}")
            
            if dry_run:
                return self._execute_dry_run(description_file, range_id, network_mode, enable_ssh)
            else:
                return self._execute_actual_creation(description_file, range_id, network_mode, enable_ssh)
                
        except Exception as e:
            self.handle_error(e, "create")
            return False
    
    def _execute_dry_run(self, description_file: Path, range_id: Optional[int],
                        network_mode: str, enable_ssh: bool) -> bool:
        """执行干运行模式"""
        self.console.print("[bold yellow]Dry run mode - will not actually create cyber range[/bold yellow]")
        
        try:
            orchestrator, provider = self.create_orchestrator(network_mode, enable_ssh)
            if not orchestrator:
                return False
            
            # For dry run, we'll validate YAML and show what would be created
            import yaml
            
            try:
                with open(description_file, 'r') as f:
                    yaml_data = yaml.safe_load(f)
                
                self.console.print(f"[green]✓[/green] YAML syntax valid")
                
                # Extract information from range description
                hosts = []
                guests = []
                range_name = description_file.stem
                
                # Parse the YAML structure (supports both list and dict formats)
                if isinstance(yaml_data, list):
                    for section in yaml_data:
                        if isinstance(section, dict):
                            if 'host_settings' in section:
                                hosts.extend(section['host_settings'])
                            if 'guest_settings' in section:
                                guests.extend(section['guest_settings'])
                            if 'clone_settings' in section:
                                for clone in section['clone_settings']:
                                    if clone.get('range_id'):
                                        range_name = clone['range_id']
                elif isinstance(yaml_data, dict):
                    if 'host_settings' in yaml_data:
                        hosts.extend(yaml_data['host_settings'])
                    if 'guest_settings' in yaml_data:
                        guests.extend(yaml_data['guest_settings'])
                    if 'clone_settings' in yaml_data:
                        for clone in yaml_data['clone_settings']:
                            if clone.get('range_id'):
                                range_name = clone['range_id']
                
                self.console.print(f"[cyan]Range Name:[/cyan] {range_name}")
                self.console.print(f"[cyan]Hosts:[/cyan] {len(hosts)}")
                self.console.print(f"[cyan]Guests:[/cyan] {len(guests)}")
                
                # Show guest details
                for i, guest in enumerate(guests):
                    guest_id = guest.get('id', f'guest-{i+1}')
                    self.console.print(f"  {i+1}. {guest_id}")
                    
                return True
            except yaml.YAMLError as e:
                self.error_display.display_error(f"YAML parsing failed: {e}")
                return False
            except Exception as e:
                self.error_display.display_error(f"YAML validation failed: {e}")
                return False
                
        except Exception as e:
            self.error_display.display_error(f"Validation error: {str(e)}")
            if self.verbose:
                import traceback
                self.error_console.print(traceback.format_exc())
            return False
    
    def _execute_actual_creation(self, description_file: Path, range_id: Optional[int],
                               network_mode: str, enable_ssh: bool) -> bool:
        """执行实际的靶场创建"""
        try:
            orchestrator, provider = self.create_orchestrator(network_mode, enable_ssh)
            if not orchestrator:
                return False
            
            self.console.print("[bold blue]Initializing cyber range creation...[/bold blue]")
            
            # Use the working create_range_from_yaml method
            with self.console.status("[bold green]Creating cyber range...") as status:
                result_range_id = orchestrator.create_range_from_yaml(
                    description_file,
                    range_id
                )
            
            if result_range_id:
                # Get the created range details for display
                range_metadata = orchestrator.get_range(result_range_id)
                
                if range_metadata:
                    self.console.print(MessageFormatter.success(
                        f"✅ Cyber range '{range_metadata.name}' created successfully!"
                    ))
                    self.console.print(f"[cyan]Range ID:[/cyan] {result_range_id}")
                    self.console.print(f"[cyan]Status:[/cyan] {range_metadata.status.value}")
                    self.console.print(f"[cyan]Created:[/cyan] {range_metadata.created_at}")
                else:
                    self.console.print(MessageFormatter.success(
                        f"✅ Cyber range '{result_range_id}' created successfully!"
                    ))
                    self.console.print(f"[cyan]Range ID:[/cyan] {result_range_id}")
                
                return True
            else:
                self.console.print(MessageFormatter.error("Cyber range creation failed"))
                return False
                
        except Exception as e:
            self.error_display.display_error(f"Error creating cyber range: {str(e)}")
            if self.verbose:
                import traceback
                self.error_console.print(traceback.format_exc())
            return False