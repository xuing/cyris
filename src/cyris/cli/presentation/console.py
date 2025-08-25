"""
Console management for CLI presentation
统一的控制台管理
"""

from rich.console import Console

# Global console instances following Rich best practices
_console = None
_error_console = None

def get_console() -> Console:
    """Get main console instance"""
    global _console
    if _console is None:
        _console = Console()
    return _console

def get_error_console() -> Console:
    """Get error console instance"""
    global _error_console
    if _error_console is None:
        _error_console = Console(stderr=True, style="bold red")
    return _error_console