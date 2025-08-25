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
                dry_run: bool = False, network_mode: str = 'user',
                enable_ssh: bool = False) -> bool:
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
            
            result = orchestrator.create_range_from_yaml(
                description_file=description_file,
                range_id=range_id,
                dry_run=True
            )
            
            if result:
                self.console.print(MessageFormatter.success(
                    f"Validation successful. Would create range: {result}"
                ))
                return True
            else:
                self.console.print(MessageFormatter.error("Validation failed"))
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
            
            result = orchestrator.create_range_from_yaml(
                description_file=description_file,
                range_id=range_id,
                dry_run=False
            )
            
            if result:
                self.console.print(MessageFormatter.success(
                    f"Cyber range created successfully: {result}"
                ))
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