"""
Base Command Handler - Provides abstract base class for command handlers
Follows OCP principle - Open for extension, closed for modification
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path

from cyris.config.settings import CyRISSettings
from cyris.cli.presentation import get_console, get_error_console, ErrorDisplayManager


class BaseCommandHandler(ABC):
    """Command handler base class - Implements common functionality, defines extension interface"""
    
    def __init__(self, config: CyRISSettings, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.console = get_console()
        self.error_console = get_error_console() 
        self.error_display = ErrorDisplayManager()
    
    @abstractmethod
    def execute(self, **kwargs) -> bool:
        """Execute command - Subclasses must implement"""
        pass
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """Unified error handling - DRY principle"""
        if context:
            self.error_display.display_command_error(context, error)
        else:
            self.error_display.display_error(str(error))
        
        if self.verbose:
            import traceback
            self.error_console.print(traceback.format_exc())
    
    def validate_range_id(self, range_id: str) -> bool:
        """Validate range ID format"""
        if not range_id or not range_id.strip():
            self.error_display.display_error("Range ID cannot be empty")
            return False
        return True
    
    def validate_file_exists(self, file_path: Path) -> bool:
        """Validate file exists"""
        if not file_path.exists():
            self.error_display.display_error(f"File not found: {file_path}")
            return False
        return True
    
    def create_orchestrator(self, network_mode: str = 'bridge', enable_ssh: bool = True):
        """Create orchestrator with singleton pattern - Reusable logic"""
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
            
            # Use singleton pattern for orchestrator
            from cyris.services.orchestrator import CyRISSingleton
            singleton = CyRISSingleton(self.config.cyber_range_dir / '.cyris.lock')
            orchestrator = RangeOrchestrator(self.config, provider)
            
            return orchestrator, provider, singleton
            
        except ImportError as e:
            self.error_display.display_error(f"Failed to import required modules: {e}")
            return None, None, None
        except Exception as e:
            self.handle_error(e, "create_orchestrator")
            return None, None, None
    
    def log_verbose(self, message: str) -> None:
        """Verbose logging output"""
        if self.verbose:
            self.console.print(f"[dim]{message}[/dim]")


class ValidationMixin:
    """Validation mixin class - Provides common validation functionality"""
    
    def validate_yaml_file(self, file_path: Path) -> bool:
        """Validate YAML file format"""
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
        """Validate network mode"""
        valid_modes = ['user', 'bridge']
        if network_mode not in valid_modes:
            self.error_display.display_error(
                f"Invalid network mode: {network_mode}. Valid options: {', '.join(valid_modes)}"
            )
            return False
        return True


class ServiceMixin:
    """Service mixin class - Provides common service access"""
    
    def get_ip_manager(self, libvirt_uri: str = "qemu:///system"):
        """Get IP manager"""
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
        """Get permission manager"""
        try:
            from cyris.infrastructure.permissions import PermissionManager
            return PermissionManager(dry_run=dry_run)
        except ImportError as e:
            self.error_display.display_error(f"Permission management not available: {e}")
            return None
        except Exception as e:
            self.handle_error(e, "get_permission_manager")
            return None