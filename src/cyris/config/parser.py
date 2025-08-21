"""
Configuration Parser Module
Supports legacy INI and modern YAML configuration formats
"""
import logging
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any, Union, Tuple, Optional

import yaml
from pydantic import ValidationError

from .settings import CyRISSettings


logger = logging.getLogger(__name__)


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