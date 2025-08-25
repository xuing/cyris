"""
配置相关命令处理器
处理config-show, config-init等命令
"""

from pathlib import Path
from typing import Optional

from .base_command import BaseCommandHandler
from cyris.cli.presentation import ConfigFormatter, MessageFormatter


class ConfigCommandHandler(BaseCommandHandler):
    """配置命令处理器 - 遵循SRP原则"""
    
    def show_config(self) -> bool:
        """显示当前配置"""
        try:
            config_items = ConfigFormatter.format_config_overview(self.config)
            
            for item in config_items:
                self.console.print(item)
            
            return True
            
        except Exception as e:
            self.handle_error(e, "show_config")
            return False
    
    def init_config(self, output_path: Path, overwrite: bool = False) -> bool:
        """初始化默认配置文件"""
        try:
            # Check if file exists
            if output_path.exists() and not overwrite:
                self.error_display.display_error(
                    f"Configuration file {output_path} already exists. Use --force to overwrite."
                )
                return False
            
            # Create default configuration
            from cyris.config.parser import create_default_config
            
            settings = create_default_config(output_path)
            
            self.console.print(MessageFormatter.success(
                f"Default configuration file created: {output_path}"
            ))
            self.console.print("[dim]Please edit the configuration file to suit your environment[/dim]")
            
            return True
            
        except ImportError as e:
            self.error_display.display_error(f"Failed to import config parser: {e}")
            return False
        except Exception as e:
            self.handle_error(e, "init_config")
            return False
    
    def execute(self, **kwargs) -> bool:
        """Execute config command based on action"""
        action = kwargs.get('action', 'show')
        
        if action == 'show':
            return self.show_config()
        elif action == 'init':
            output_path = kwargs.get('output_path', Path('config.yml'))
            overwrite = kwargs.get('overwrite', False)
            return self.init_config(output_path, overwrite)
        else:
            self.error_display.display_error(f"Unknown config action: {action}")
            return False