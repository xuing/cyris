"""
Rich text formatters for CLI output
复用的格式化器，遵循DRY原则
"""

from typing import Optional
from rich.text import Text
from rich.markup import escape
from cyris.config.settings import CyRISSettings


class StatusFormatter:
    """状态指示器格式化器 - 复用状态显示逻辑"""
    
    # Status style mappings
    _styles = {
        'active': (':green_circle:', 'green'),
        'creating': (':yellow_circle:', 'yellow'), 
        'error': (':red_circle:', 'red'),
        'ok': (':check_mark:', 'green'),
        'fail': (':cross_mark:', 'red'),
        'warning': (':warning:', 'orange3'),
        'info': (':information:', 'blue'),
        'running': (':arrow_forward:', 'green'),
        'stopped': (':stop_button:', 'red'),
        'healthy': (':green_heart:', 'green'),
        'unhealthy': (':cross_mark:', 'red')
    }
    
    @classmethod
    def format_status(cls, status: str, label: Optional[str] = None) -> Text:
        """Format status with emoji and color"""
        status_lower = status.lower()
        label_text = escape(label or status)
        
        if status_lower in cls._styles:
            emoji, color = cls._styles[status_lower]
            return Text.assemble(
                (emoji, color),
                (" ", ""),
                (label_text, color)
            )
        else:
            return Text.assemble(
                ("•", "dim"),
                (" ", ""),
                (label_text, "dim")
            )


class ConfigFormatter:
    """配置显示格式化器"""
    
    @staticmethod
    def format_config_item(label: str, value: str, style: str = "cyan") -> Text:
        """Format configuration item"""
        return Text.assemble(
            (f"  {label}: ", "dim"),
            (value, style)
        )
    
    @staticmethod
    def format_config_overview(config: CyRISSettings) -> list[Text]:
        """Format complete configuration overview"""
        items = []
        
        items.append(Text("Current configuration:", style="bold blue"))
        items.append(ConfigFormatter.format_config_item(
            "CyRIS path", str(config.cyris_path)
        ))
        items.append(ConfigFormatter.format_config_item(
            "Cyber range directory", str(config.cyber_range_dir)
        ))
        items.append(ConfigFormatter.format_config_item(
            "Gateway mode", 
            "enabled" if config.gw_mode else "disabled",
            "green" if config.gw_mode else "red"
        ))
        
        # Optional fields
        if config.gw_account:
            items.append(ConfigFormatter.format_config_item(
                "Gateway account", config.gw_account, "yellow"
            ))
        if config.gw_mgmt_addr:
            items.append(ConfigFormatter.format_config_item(
                "Gateway management address", config.gw_mgmt_addr, "yellow"
            ))
        if config.user_email:
            items.append(ConfigFormatter.format_config_item(
                "User email", config.user_email, "yellow"
            ))
            
        return items


class MessageFormatter:
    """通用消息格式化器"""
    
    @staticmethod
    def success(message: str) -> Text:
        """Format success message"""
        return Text.assemble(
            ("[OK] ", "bold green"),
            (message, "green")
        )
    
    @staticmethod 
    def error(message: str) -> Text:
        """Format error message"""
        return Text.assemble(
            ("[ERROR] ", "bold red"),
            (message, "red")
        )
    
    @staticmethod
    def warning(message: str) -> Text:
        """Format warning message"""
        return Text.assemble(
            ("[WARNING] ", "bold yellow"),
            (message, "yellow")
        )
    
    @staticmethod
    def info(message: str) -> Text:
        """Format info message"""  
        return Text.assemble(
            ("[INFO] ", "bold blue"),
            (message, "blue")
        )