"""
CLI Presentation Layer - 显示层
负责所有Rich格式化和输出显示逻辑
"""

from .formatters import StatusFormatter, ConfigFormatter, MessageFormatter
from .display import RangeDisplayManager, ErrorDisplayManager
from .console import get_console, get_error_console

__all__ = [
    'StatusFormatter',
    'ConfigFormatter',
    'MessageFormatter',
    'RangeDisplayManager',
    'ErrorDisplayManager',
    'get_console',
    'get_error_console'
]