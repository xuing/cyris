"""
基础命令处理器 - 提供命令处理器的抽象基类
遵循OCP原则 - 对扩展开放，对修改封闭
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path

from cyris.config.settings import CyRISSettings
from cyris.cli.presentation import get_console, get_error_console, ErrorDisplayManager


class BaseCommandHandler(ABC):
    """命令处理器基类 - 实现通用功能，定义扩展接口"""
    
    def __init__(self, config: CyRISSettings, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.console = get_console()
        self.error_console = get_error_console() 
        self.error_display = ErrorDisplayManager()
    
    @abstractmethod
    def execute(self, **kwargs) -> bool:
        """执行命令 - 子类必须实现"""
        pass
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """统一的错误处理 - DRY原则"""
        if context:
            self.error_display.display_command_error(context, error)
        else:
            self.error_display.display_error(str(error))
        
        if self.verbose:
            import traceback
            self.error_console.print(traceback.format_exc())
    
    def validate_range_id(self, range_id: str) -> bool:
        """验证靶场ID格式"""
        if not range_id or not range_id.strip():
            self.error_display.display_error("Range ID cannot be empty")
            return False
        return True
    
    def validate_file_exists(self, file_path: Path) -> bool:
        """验证文件存在"""
        if not file_path.exists():
            self.error_display.display_error(f"File not found: {file_path}")
            return False
        return True
    
    def create_orchestrator(self, network_mode: str = 'user', enable_ssh: bool = False):
        """创建编排器 - 复用逻辑"""
        try:
            from cyris.services.orchestrator import RangeOrchestrator
            from cyris.infrastructure.providers.kvm_provider import KVMProvider
            
            # Configure network settings
            libvirt_uri = 'qemu:///system' if network_mode == 'bridge' else 'qemu:///session'
            
            kvm_settings = {
                'connection_uri': libvirt_uri,
                'libvirt_uri': libvirt_uri,
                'base_path': str(self.config.cyber_range_dir),
                'network_mode': network_mode,
                'enable_ssh': enable_ssh
            }
            
            provider = KVMProvider(kvm_settings)
            orchestrator = RangeOrchestrator(self.config, provider)
            
            return orchestrator, provider
            
        except ImportError as e:
            self.error_display.display_error(f"Failed to import required modules: {e}")
            return None, None
        except Exception as e:
            self.handle_error(e, "create_orchestrator")
            return None, None
    
    def log_verbose(self, message: str) -> None:
        """详细日志输出"""
        if self.verbose:
            self.console.print(f"[dim]{message}[/dim]")


class ValidationMixin:
    """验证混入类 - 提供通用验证功能"""
    
    def validate_yaml_file(self, file_path: Path) -> bool:
        """验证YAML文件格式"""
        try:
            import yaml
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            return True
        except yaml.YAMLError as e:
            self.error_display.display_error(f"Invalid YAML format: {e}")
            return False
        except Exception as e:
            self.handle_error(e, f"validate_yaml_file({file_path})")
            return False
    
    def validate_network_mode(self, network_mode: str) -> bool:
        """验证网络模式"""
        valid_modes = ['user', 'bridge']
        if network_mode not in valid_modes:
            self.error_display.display_error(
                f"Invalid network mode: {network_mode}. Valid options: {', '.join(valid_modes)}"
            )
            return False
        return True


class ServiceMixin:
    """服务混入类 - 提供通用服务访问"""
    
    def get_ip_manager(self, libvirt_uri: str = "qemu:///system"):
        """获取IP管理器"""
        try:
            from cyris.tools.vm_ip_manager import VMIPManager
            return VMIPManager(libvirt_uri=libvirt_uri)
        except ImportError:
            if self.verbose:
                self.console.print("[yellow]VM IP management not available[/yellow]")
            return None
        except Exception as e:
            self.handle_error(e, "get_ip_manager")
            return None
    
    def get_permission_manager(self, dry_run: bool = False):
        """获取权限管理器"""
        try:
            from cyris.infrastructure.permissions import PermissionManager
            return PermissionManager(dry_run=dry_run)
        except ImportError as e:
            self.error_display.display_error(f"Permission management not available: {e}")
            return None
        except Exception as e:
            self.handle_error(e, "get_permission_manager")
            return None