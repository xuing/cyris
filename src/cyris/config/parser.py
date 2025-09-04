"""
Configuration Parser Module
Supports legacy INI and modern YAML configuration formats
"""
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any, Union, Tuple, Optional

import yaml
from pydantic import ValidationError

from .settings import CyRISSettings
from ..domain.entities.host import Host, HostBuilder
from ..domain.entities.guest import Guest, GuestBuilder, OSType, BaseVMType


logger = get_logger(__name__, "parser")


class ConfigurationError(Exception):
    """Configuration-related errors"""
    pass


def parse_legacy_config(config_file: Union[str, Path]) -> Tuple[
    Optional[str], Optional[str], bool, Optional[str], 
    Optional[str], Optional[str], Optional[str]
]:
    """
    Parse legacy INI format configuration file
    Maintain compatibility with original parse_config function
    
    Returns:
        tuple: (abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email)
    """
    config_file = Path(config_file)
    
    if not config_file.exists():
        logger.error(f"Configuration file not found: {config_file}")
        return tuple([False] * 7)
    
    try:
        config = ConfigParser()
        config.read(config_file)
        
        section_name = "config"
        if not config.has_section(section_name):
            raise ConfigurationError(f"Missing [{section_name}] section in config file")
        
        # Parse individual configuration items
        abs_path = config.get(section_name, "cyris_path", fallback=None)
        cr_dir = config.get(section_name, "cyber_range_dir", fallback=None)
        
        # Special handling for gw_mode
        gw_mode_str = config.get(section_name, "gw_mode", fallback="off")
        gw_mode = gw_mode_str.lower() not in ('off', 'false', '0', 'no')
        
        gw_account = config.get(section_name, "gw_account", fallback=None)
        gw_mgmt_addr = config.get(section_name, "gw_mgmt_addr", fallback=None)  
        gw_inside_addr = config.get(section_name, "gw_inside_addr", fallback=None)
        user_email = config.get(section_name, "user_email", fallback=None)
        
        logger.debug(f"Parsed config: cyris_path={abs_path}, gw_mode={gw_mode}")
        
        return abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email
        
    except Exception as e:
        logger.error(f"Error parsing config file {config_file}: {e}")
        return tuple([False] * 7)


def parse_modern_config(config_file: Union[str, Path]) -> CyRISSettings:
    """
    Parse modern YAML format configuration file
    
    Args:
        config_file: Configuration file path
        
    Returns:
        CyRISSettings: Parsed configuration object
        
    Raises:
        ConfigurationError: Configuration file parsing or validation failed
    """
    config_file = Path(config_file)
    
    if not config_file.exists():
        raise ConfigurationError(f"Configuration file not found: {config_file}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            if config_file.suffix.lower() in ['.yml', '.yaml']:
                config_data = yaml.safe_load(f)
            else:
                # Try parsing as INI format and convert
                legacy_result = parse_legacy_config(config_file)
                if legacy_result[0] is False:
                    raise ConfigurationError("Failed to parse legacy config")
                
                abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email = legacy_result
                
                config_data = {
                    'cyris_path': abs_path or str(Path.cwd()),
                    'cyber_range_dir': cr_dir or str(Path.cwd() / 'cyber_range'),
                    'gw_mode': gw_mode,
                    'gw_account': gw_account,
                    'gw_mgmt_addr': gw_mgmt_addr,
                    'gw_inside_addr': gw_inside_addr,
                    'user_email': user_email
                }
        
        return CyRISSettings(**config_data)
        
    except ValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e}")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"YAML parsing error: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error parsing config file: {e}")


def create_default_config(config_file: Union[str, Path]) -> CyRISSettings:
    """
    Create default configuration file
    
    Args:
        config_file: Configuration file path
        
    Returns:
        CyRISSettings: Default configuration object
    """
    config_file = Path(config_file)
    settings = CyRISSettings()
    
    # Create YAML format configuration file
    config_data = {
        'cyris_path': str(settings.cyris_path),
        'cyber_range_dir': str(settings.cyber_range_dir),
        'gw_mode': settings.gw_mode,
        'gw_account': settings.gw_account,
        'gw_mgmt_addr': settings.gw_mgmt_addr,
        'gw_inside_addr': settings.gw_inside_addr,
        'user_email': settings.user_email
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, default_flow_style=False, indent=2)
    
    logger.info(f"Created default config file: {config_file}")
    return settings


class YAMLParseResult:
    """Result object from YAML parsing"""
    
    def __init__(self, hosts: list, guests: list, clone_settings: dict):
        self.hosts = hosts
        self.guests = guests
        self.clone_settings = clone_settings


class CyRISConfigParser:
    """
    YAML Configuration Parser
    Parses CyRIS YAML description files into domain entities
    """
    
    def parse_file(self, yaml_file: Union[str, Path]) -> YAMLParseResult:
        """
        Parse YAML description file
        
        Args:
            yaml_file: Path to YAML description file
            
        Returns:
            YAMLParseResult: Parsed hosts, guests, and clone settings
            
        Raises:
            ConfigurationError: If parsing fails
        """
        yaml_file = Path(yaml_file)
        
        if not yaml_file.exists():
            raise ConfigurationError(f"YAML file not found: {yaml_file}")
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            hosts = []
            guests = []
            clone_settings = {}
            
            # Handle list-based YAML structure where each section is a list item
            if isinstance(yaml_data, list):
                for section in yaml_data:
                    if isinstance(section, dict):
                        # Parse host settings
                        if 'host_settings' in section:
                            for host_data in section['host_settings']:
                                host = self._parse_host(host_data)
                                if host:
                                    hosts.append(host)
                        
                        # Parse guest settings  
                        if 'guest_settings' in section:
                            for guest_data in section['guest_settings']:
                                guest = self._parse_guest(guest_data)
                                if guest:
                                    guests.append(guest)
                        
                        # Parse clone settings
                        if 'clone_settings' in section:
                            clone_settings = section['clone_settings']
            
            # Handle dictionary-based YAML structure
            elif isinstance(yaml_data, dict):
                # Parse host settings
                if 'host_settings' in yaml_data:
                    for host_data in yaml_data['host_settings']:
                        host = self._parse_host(host_data)
                        if host:
                            hosts.append(host)
                
                # Parse guest settings  
                if 'guest_settings' in yaml_data:
                    for guest_data in yaml_data['guest_settings']:
                        guest = self._parse_guest(guest_data)
                        if guest:
                            guests.append(guest)
                
                # Parse clone settings
                if 'clone_settings' in yaml_data:
                    clone_settings = yaml_data['clone_settings']
            
            return YAMLParseResult(hosts, guests, clone_settings)
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"YAML parsing error: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error parsing YAML file: {e}")
    
    def _parse_host(self, host_data: dict) -> Optional[Host]:
        """Parse host configuration from YAML data"""
        try:
            return Host(
                host_id=host_data.get('name', host_data.get('id', 'unknown')),
                mgmt_addr=host_data.get('mgmt_addr', '127.0.0.1'),
                virbr_addr=host_data.get('virbr_addr', '192.168.122.1'),
                account=host_data.get('account', 'root')
            )
        except Exception as e:
            logger.warning(f"Failed to parse host: {e}")
            return None
    
    def _parse_guest(self, guest_data: dict) -> Optional[Guest]:
        """Parse guest configuration from YAML data"""
        guest_id = guest_data.get('id', guest_data.get('name', 'unknown'))
        logger.debug(f"[DEBUG] _parse_guest START: id={guest_id}, basevm_type={guest_data.get('basevm_type', 'no-type')}")
        try:
            # Map common OS strings to OSType enum values
            os_type_mapping = {
                'ubuntu.20.04': OSType.UBUNTU_20,
                'ubuntu.18.04': OSType.UBUNTU_18,
                'ubuntu.16.04': OSType.UBUNTU_16,
                'ubuntu': OSType.UBUNTU,
                'windows.7': OSType.WINDOWS_7,
                'windows.10': OSType.WINDOWS_10,
                'centos': OSType.CENTOS
            }
            
            # Try multiple field names for OS type
            os_type_str = guest_data.get('basevm_os_type', guest_data.get('os_type', 'ubuntu'))
            os_type = os_type_mapping.get(os_type_str, OSType.UBUNTU)
            
            # Map basevm_type including kvm-auto
            basevm_type_mapping = {
                'kvm': BaseVMType.KVM,
                'aws': BaseVMType.AWS,
                'docker': BaseVMType.DOCKER,
                'kvm-auto': BaseVMType.KVM_AUTO
            }
            basevm_type_str = guest_data.get('basevm_type', 'kvm')
            basevm_type = basevm_type_mapping.get(basevm_type_str, BaseVMType.KVM)
            
            # Extract all tasks from the tasks list if it exists
            tasks = []
            if 'tasks' in guest_data and isinstance(guest_data['tasks'], list):
                for task_item in guest_data['tasks']:
                    if isinstance(task_item, dict):
                        tasks.append(task_item)
            
            # For kvm-auto, some fields are optional, for others they are required
            if basevm_type == BaseVMType.KVM_AUTO:
                logger.debug(f"[DEBUG] Creating KVM_AUTO guest with image_name={guest_data.get('image_name', 'no-image')}")
                # kvm-auto specific validation will be done by Guest model validators
                logger.debug(f"[DEBUG] About to instantiate Guest entity for kvm-auto")
                guest_instance = Guest(
                    guest_id=guest_data.get('name', guest_data.get('id', 'unknown')),
                    basevm_host=guest_data.get('basevm_host'),  # Optional for kvm-auto
                    basevm_config_file=guest_data.get('basevm_config_file'),  # Optional for kvm-auto  
                    basevm_os_type=os_type,  # Will be auto-derived if not provided
                    basevm_type=basevm_type,
                    ip_addr=guest_data.get('ip_addr'),
                    tasks=tasks,
                    # kvm-auto specific fields
                    image_name=guest_data.get('image_name'),
                    vcpus=guest_data.get('vcpus'),
                    memory=guest_data.get('memory'),
                    disk_size=guest_data.get('disk_size'),
                    # Enhanced kvm-auto configuration options
                    graphics_type=guest_data.get('graphics_type', 'vnc'),
                    graphics_port=guest_data.get('graphics_port'),
                    graphics_listen=guest_data.get('graphics_listen', '127.0.0.1'),
                    console_type=guest_data.get('console_type', 'pty'),
                    network_model=guest_data.get('network_model', 'virtio'),
                    os_variant=guest_data.get('os_variant'),
                    boot_options=guest_data.get('boot_options'),
                    cpu_model=guest_data.get('cpu_model'),
                    extra_args=guest_data.get('extra_args')
                )
            else:
                # Regular guest types - use defaults for missing required fields
                return Guest(
                    guest_id=guest_data.get('name', guest_data.get('id', 'unknown')),
                    basevm_host=guest_data.get('basevm_host', 'localhost'),
                    basevm_config_file=guest_data.get('basevm_config_file', '/tmp/base.xml'),
                    basevm_os_type=os_type,
                    basevm_type=basevm_type,
                    ip_addr=guest_data.get('ip_addr'),
                    tasks=tasks
                )
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse guest {guest_id}: {e}")
            logger.error(f"[ERROR] Guest data was: {guest_data}")
            import traceback
            logger.error(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            return None