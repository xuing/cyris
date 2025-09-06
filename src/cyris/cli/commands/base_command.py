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
        # Initialize logger using unified logging system
        from cyris.core.unified_logger import get_logger
        self.logger = get_logger(__name__, "base_command")
        
        self.config = config
        self.verbose = verbose
        
        self.logger.debug("BaseCommandHandler.__init__() START")
        self.logger.debug("About to initialize console components")
        
        self.console = get_console()
        self.error_console = get_error_console()
        self.error_display = ErrorDisplayManager()
        
        self.logger.debug("BaseCommandHandler.__init__() COMPLETE")
    
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
        self.logger.debug(f"validate_file_exists() called with: {file_path}")
        
        if not file_path.exists():
            self.logger.debug(f"File does not exist: {file_path}")
            self.error_display.display_error(f"File not found: {file_path}")
            return False
        
        self.logger.debug(f"File exists: {file_path}")
        return True
    
    def create_orchestrator(self, network_mode: str = 'bridge', enable_ssh: bool = True):
        """Create orchestrator with singleton pattern - Reusable logic"""
        self.logger.debug(f"create_orchestrator() START with network_mode={network_mode}, enable_ssh={enable_ssh}")
            
        try:
            self.logger.debug("About to import RangeOrchestrator")
            from cyris.services.orchestrator import RangeOrchestrator
            self.logger.debug("RangeOrchestrator imported successfully")
                
            self.logger.debug("About to import KVMProvider")
            from cyris.infrastructure.providers.kvm_provider import KVMProvider
            self.logger.debug("KVMProvider imported successfully")
            
            # Configure network settings
            self.logger.debug("About to configure network settings")
            libvirt_uri = 'qemu:///system' if network_mode == 'bridge' else 'qemu:///session'
            self.logger.debug(f"libvirt_uri set to: {libvirt_uri}")
            
            kvm_settings = {
                'connection_uri': libvirt_uri,
                'libvirt_uri': libvirt_uri,
                'base_path': str(self.config.cyber_range_dir),
                'network_mode': network_mode,
                'enable_ssh': enable_ssh,
                'build_storage_dir': str(self.config.build_storage_dir),
                'vm_storage_dir': str(self.config.vm_storage_dir)
            }
            
            self.logger.debug(f"kvm_settings created: {kvm_settings}")
            self.logger.debug("About to create KVMProvider instance")
            provider = KVMProvider(kvm_settings)
            self.logger.debug("KVMProvider instance created successfully")
            
            # Use singleton pattern for orchestrator
            self.logger.debug("About to import CyRISSingleton")
            from cyris.services.orchestrator import CyRISSingleton
            self.logger.debug("CyRISSingleton imported successfully")
                
            self.logger.debug(f"About to create CyRISSingleton with lock file: {self.config.cyber_range_dir / '.cyris.lock'}")
            singleton = CyRISSingleton(self.config.cyber_range_dir / '.cyris.lock')
            self.logger.debug("CyRISSingleton created successfully")
                
            self.logger.debug("About to create RangeOrchestrator instance")
            orchestrator = RangeOrchestrator(self.config, provider)
            self.logger.debug("RangeOrchestrator instance created successfully")
            
            self.logger.debug("create_orchestrator() completed successfully")
            return orchestrator, provider, singleton
            
        except ImportError as e:
            self.logger.debug(f"ImportError in create_orchestrator: {e}")
            self.error_display.display_error(f"Failed to import required modules: {e}")
            return None, None, None
        except Exception as e:
            self.logger.debug(f"Exception in create_orchestrator: {e}")
            self.handle_error(e, "create_orchestrator")
            return None, None, None
    
    def log_verbose(self, message: str) -> None:
        """Verbose logging output"""
        if self.verbose:
            self.console.print(f"[dim]{message}[/dim]")
    
    # Validation methods (formerly ValidationMixin)
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
    
    # Service access methods (formerly ServiceMixin)
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