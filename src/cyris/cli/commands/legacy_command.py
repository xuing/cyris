"""
Legacy命令处理器
处理传统CyRIS命令兼容性
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple

from .base_command import BaseCommandHandler
from cyris.cli.presentation import MessageFormatter


class LegacyCommandHandler(BaseCommandHandler):
    """Legacy命令处理器 - 传统CyRIS命令兼容性"""
    
    def execute(self, args: Tuple[str, ...]) -> bool:
        """执行legacy命令"""
        try:
            if not args:
                self.console.print("[yellow]Usage: cyris legacy <description_file> <config_file> [options][/yellow]")
                self.console.print("\nThis command provides compatibility with the original CyRIS interface:")
                self.console.print("  [cyan]cyris legacy examples/basic.yml CONFIG[/cyan]")
                return False
            
            legacy_script = self.config.cyris_path / 'main' / 'cyris.py'
            
            if not legacy_script.exists():
                self.console.print(MessageFormatter.error(
                    f"Legacy script does not exist: {legacy_script}"
                ))
                return False
            
            self.console.print(f"[blue]Running legacy CyRIS command...[/blue]")
            if self.verbose:
                self.log_verbose(f"Legacy script: {legacy_script}")
                self.log_verbose(f"Arguments: {' '.join(args)}")
            
            # Build and execute command
            success = self._execute_legacy_command(legacy_script, args)
            
            if success:
                self.console.print(MessageFormatter.success(
                    "Legacy command completed successfully"
                ))
            else:
                self.console.print(MessageFormatter.error(
                    "Legacy command failed"
                ))
            
            return success
            
        except Exception as e:
            self.handle_error(e, "legacy")
            return False
    
    def _execute_legacy_command(self, legacy_script: Path, args: Tuple[str, ...]) -> bool:
        """执行传统命令"""
        try:
            # Build command
            cmd = ['python3', str(legacy_script)] + list(args)
            
            if self.verbose:
                self.console.print(f"[dim]Executing: {' '.join(cmd)}[/dim]")
            
            # Execute command with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output in real-time
            for line in process.stdout:
                print(line.rstrip())  # Use print() to bypass Rich formatting
            
            # Wait for completion
            return_code = process.wait()
            
            return return_code == 0
            
        except subprocess.CalledProcessError as e:
            self.console.print(MessageFormatter.error(
                f"Legacy command failed with exit code {e.returncode}"
            ))
            if self.verbose and e.output:
                self.console.print(f"[dim]Output: {e.output}[/dim]")
            return False
            
        except FileNotFoundError:
            self.console.print(MessageFormatter.error(
                "Python3 not found. Please ensure Python 3 is installed."
            ))
            return False
            
        except Exception as e:
            self.console.print(MessageFormatter.error(
                f"Failed to execute legacy command: {str(e)}"
            ))
            return False
    
    def _validate_legacy_args(self, args: Tuple[str, ...]) -> bool:
        """验证传统命令参数"""
        if len(args) < 2:
            self.console.print("[yellow]Legacy commands require at least 2 arguments: <description_file> <config_file>[/yellow]")
            return False
        
        description_file = Path(args[0])
        config_file = Path(args[1])
        
        if not description_file.exists():
            self.console.print(MessageFormatter.error(
                f"Description file does not exist: {description_file}"
            ))
            return False
        
        if not config_file.exists():
            self.console.print(MessageFormatter.error(
                f"Config file does not exist: {config_file}"
            ))
            return False
        
        return True