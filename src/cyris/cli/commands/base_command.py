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
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] BaseCommandHandler.__init__() START\n")
            f.flush()
        
        self.config = config
        self.verbose = verbose
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] About to call get_console()\n")
            f.flush()
        
        self.console = get_console()
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] About to call get_error_console()\n")
            f.flush()
        
        self.error_console = get_error_console()
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] About to create ErrorDisplayManager()\n")
            f.flush()
            
        self.error_display = ErrorDisplayManager()
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] BaseCommandHandler.__init__() COMPLETE\n")
            f.flush()
    
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
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] validate_file_exists() called with: {file_path}\n")
            f.flush()
        
        if not file_path.exists():
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] File does not exist: {file_path}\n")
                f.flush()
            self.error_display.display_error(f"File not found: {file_path}")
            return False
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] File exists: {file_path}\n")
            f.flush()
        return True
    
    def create_orchestrator(self, network_mode: str = 'bridge', enable_ssh: bool = True):
        """Create orchestrator with singleton pattern - Reusable logic"""
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] create_orchestrator() START with network_mode={network_mode}, enable_ssh={enable_ssh}\n")
            f.flush()
            
        try:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] About to import RangeOrchestrator\n")
                f.flush()
                
            from cyris.services.orchestrator import RangeOrchestrator
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] RangeOrchestrator imported successfully\n")
                f.flush()
                
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] About to import KVMProvider\n")
                f.flush()
                
            from cyris.infrastructure.providers.kvm_provider import KVMProvider
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] KVMProvider imported successfully\n")
                f.flush()
            
            # Configure network settings
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] About to configure network settings\n")
                f.flush()
                
            libvirt_uri = 'qemu:///system' if network_mode == 'bridge' else 'qemu:///session'
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] libvirt_uri set to: {libvirt_uri}\n")
                f.flush()
            
            kvm_settings = {
                'connection_uri': libvirt_uri,
                'libvirt_uri': libvirt_uri,
                'base_path': str(self.config.cyber_range_dir),
                'network_mode': network_mode,
                'enable_ssh': enable_ssh
            }
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] kvm_settings created: {kvm_settings}\n")
                f.flush()
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] About to create KVMProvider instance\n")
                f.flush()
                
            provider = KVMProvider(kvm_settings)
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] KVMProvider instance created successfully\n")
                f.flush()
            
            # Use singleton pattern for orchestrator
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] About to import CyRISSingleton\n")
                f.flush()
                
            from cyris.services.orchestrator import CyRISSingleton
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] CyRISSingleton imported successfully\n")
                f.flush()
                
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] About to create CyRISSingleton with lock file: {self.config.cyber_range_dir / '.cyris.lock'}\n")
                f.flush()
                
            singleton = CyRISSingleton(self.config.cyber_range_dir / '.cyris.lock')
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] CyRISSingleton created successfully\n")
                f.flush()
                
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] About to create RangeOrchestrator instance\n")
                f.flush()
                
            orchestrator = RangeOrchestrator(self.config, provider)
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] RangeOrchestrator instance created successfully\n")
                f.flush()
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write("[DEBUG] create_orchestrator() completed successfully\n")
                f.flush()
            
            return orchestrator, provider, singleton
            
        except ImportError as e:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] ImportError in create_orchestrator: {e}\n")
                f.flush()
            self.error_display.display_error(f"Failed to import required modules: {e}")
            return None, None, None
        except Exception as e:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] Exception in create_orchestrator: {e}\n")
                f.flush()
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
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] validate_yaml_file() called with: {file_path}\n")
            f.flush()
        
        try:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] About to import yaml\n")
                f.flush()
            
            import yaml
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] About to open and read YAML file: {file_path}\n")
                f.flush()
            
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] YAML file parsed successfully: {file_path}\n")
                f.flush()
            
            return True
        except yaml.YAMLError as e:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] YAML parsing error: {e}\n")
                f.flush()
            self.error_display.display_error(f"Invalid YAML format: {e}")
            return False
        except Exception as e:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] Exception in validate_yaml_file: {e}\n")
                f.flush()
            self.handle_error(e, f"validate_yaml_file({file_path})")
            return False
    
    def validate_network_mode(self, network_mode: str) -> bool:
        """Validate network mode"""
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] validate_network_mode() called with: {network_mode}\n")
            f.flush()
        
        valid_modes = ['user', 'bridge']
        if network_mode not in valid_modes:
            with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
                f.write(f"[DEBUG] Invalid network mode: {network_mode}, valid modes: {valid_modes}\n")
                f.flush()
            self.error_display.display_error(
                f"Invalid network mode: {network_mode}. Valid options: {', '.join(valid_modes)}"
            )
            return False
        
        with open('/home/ubuntu/cyris/debug_main.log', 'a') as f:
            f.write(f"[DEBUG] Network mode validation passed: {network_mode}\n")
            f.flush()
        
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