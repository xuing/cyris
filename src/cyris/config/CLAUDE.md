# Config Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **config**

## Module Responsibilities

The Config module manages system configuration through Pydantic-based settings validation and multi-format configuration parsing. It supports both legacy INI format (backward compatibility) and modern YAML configurations, providing a unified interface for system configuration management across different deployment scenarios.

## Entry and Startup

- **Primary Entry**: `settings.py` - Pydantic-based configuration model with validation
- **Parser Engine**: `parser.py` - Multi-format configuration parser (INI, YAML, environment)
- **Module Registration**: `__init__.py` - Configuration exports and defaults

### Config Architecture
```
config/
├── settings.py              # Pydantic configuration model with validation
├── parser.py               # Multi-format config parser (INI/YAML/ENV)
└── __init__.py             # Config module exports and defaults
```

## External Interfaces

### Settings API (Primary Interface)
```python
class CyRISSettings(BaseSettings):
    """Main configuration class with Pydantic validation"""
    
    # Core paths
    cyris_path: Path = Field(default=Path.cwd())
    cyber_range_dir: Path = Field(default=Path.cwd() / "cyber_range")
    
    # Gateway configuration  
    gw_mode: bool = Field(default=False)
    gw_account: Optional[str] = Field(default=None)
    gw_mgmt_addr: Optional[str] = Field(default=None)
    gw_inside_addr: Optional[str] = Field(default=None)
    
    # User configuration
    user_email: Optional[str] = Field(default=None)
    
    # Environment variable support
    class Config:
        env_prefix = "CYRIS_"
        env_file = ".env"
```

### Parser API (Multi-Format Support)
```python
def parse_modern_config(config_path: Path) -> CyRISSettings:
    """Parse YAML configuration files"""
    
def parse_legacy_config(config_file: Union[str, Path]) -> Tuple[...]:
    """Parse legacy INI configuration files"""
    
def parse_yaml_description(yaml_path: Path) -> Dict[str, Any]:
    """Parse YAML cyber range description files"""
    
def validate_configuration(config: CyRISSettings) -> bool:
    """Validate configuration completeness and consistency"""
```

### Environment Variable Support
```bash
# Environment variable configuration
export CYRIS_CYRIS_PATH="/opt/cyris"
export CYRIS_CYBER_RANGE_DIR="/opt/cyris/ranges"
export CYRIS_GW_MODE="true"
export CYRIS_GW_ACCOUNT="gateway"
export CYRIS_GW_MGMT_ADDR="10.0.1.1"
export CYRIS_USER_EMAIL="admin@example.com"
```

## Key Dependencies and Configuration

### External Dependencies
```python
pydantic>=2.0          # Configuration validation and parsing
pydantic-settings>=2.0 # Environment variable and file parsing
PyYAML>=6.0           # YAML parsing support
configparser          # INI file parsing (standard library)
pathlib               # Path handling (standard library)
```

### Internal Dependencies
- `domain.entities` - Entity validation for parsed configurations
- No dependencies on infrastructure or services (clean architecture)

### Configuration Sources (Priority Order)
1. **Environment Variables** - `CYRIS_*` prefixed variables
2. **Configuration Files** - YAML/INI files specified via command line
3. **Default Locations** - `config.yml`, `config.yaml`, `CONFIG` in current directory
4. **Built-in Defaults** - Hardcoded fallback values

### Configuration Validation
```python
class ConfigValidator:
    """Configuration validation and consistency checking"""
    
    @field_validator('cyris_path')
    @classmethod
    def validate_cyris_path(cls, v: Path) -> Path:
        """Ensure CyRIS path exists and is accessible"""
        
    @field_validator('gw_mgmt_addr')  
    @classmethod
    def validate_gateway_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate gateway management address format"""
        
    @model_validator(mode='after')
    def validate_gateway_consistency(self) -> 'CyRISSettings':
        """Ensure gateway configuration is consistent"""
```

## Data Models

### Configuration Schemas
```python
class CyRISSettings(BaseSettings):
    """Main configuration with validation"""
    
    # Core system paths
    cyris_path: Path = Field(description="CyRIS installation directory")
    cyber_range_dir: Path = Field(description="Cyber range storage directory")
    
    # Gateway configuration
    gw_mode: bool = Field(description="Enable gateway mode")
    gw_account: Optional[str] = Field(description="Gateway account name")
    gw_mgmt_addr: Optional[str] = Field(description="Gateway management address") 
    gw_inside_addr: Optional[str] = Field(description="Gateway internal address")
    
    # User configuration
    user_email: Optional[str] = Field(description="User email for notifications")
    
    # Advanced settings
    log_level: str = Field(default="INFO", description="Logging level")
    max_concurrent_ranges: int = Field(default=10, description="Max concurrent ranges")
    default_timeout: int = Field(default=300, description="Default operation timeout")
```

### Legacy Configuration Support
```python
@dataclass
class LegacyConfigResult:
    """Legacy INI configuration parsing result"""
    abs_path: Optional[str]
    cr_dir: Optional[str] 
    gw_mode: bool
    gw_account: Optional[str]
    gw_mgmt_addr: Optional[str]
    gw_inside_addr: Optional[str]
    user_email: Optional[str]
    
    def to_modern_settings(self) -> CyRISSettings:
        """Convert legacy config to modern settings"""
```

### YAML Description Models
```python
@dataclass
class YAMLDescription:
    """YAML cyber range description structure"""
    host_settings: List[Dict[str, Any]]
    guest_settings: List[Dict[str, Any]]  
    clone_settings: List[Dict[str, Any]]
    
    def validate_structure(self) -> bool:
        """Validate YAML description structure"""
        
    def extract_entities(self) -> Tuple[List[Host], List[Guest]]:
        """Extract domain entities from YAML"""
```

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_config_parser.py` - Configuration parsing and validation
- `/home/ubuntu/cyris/tests/unit/test_settings_validation.py` - Pydantic validation testing
- `/home/ubuntu/cyris/tests/unit/test_legacy_config.py` - Legacy format compatibility testing

### Integration Tests
- `/home/ubuntu/cyris/tests/integration/test_config_integration.py` - Configuration integration with other modules
- Test configuration loading from multiple sources
- Validate configuration precedence and override behavior

### Configuration Testing Strategy
```python
class TestConfigurationParsing:
    """Configuration testing patterns"""
    
    def test_yaml_configuration_parsing(self):
        """Test modern YAML configuration parsing"""
        
    def test_ini_configuration_parsing(self):
        """Test legacy INI configuration parsing"""
        
    def test_environment_variable_override(self):
        """Test environment variable precedence"""
        
    def test_configuration_validation_errors(self):
        """Test validation error handling"""
        
    def test_configuration_migration(self):
        """Test legacy to modern configuration migration"""
```

### Quality Requirements
- **Validation Coverage**: 100% of configuration fields must have validation
- **Backward Compatibility**: Support all legacy INI configuration formats
- **Error Reporting**: Clear, actionable error messages for invalid configurations
- **Performance**: Configuration loading < 100ms for typical configurations

## Frequently Asked Questions (FAQ)

### Q: How does configuration precedence work?
A: Environment variables > Config files > Default values. Within config files, command-line specified files take precedence over auto-discovered ones.

### Q: Can I mix INI and YAML configuration formats?
A: No, each configuration source uses one format. However, you can migrate from INI to YAML using the parser utilities.

### Q: How are sensitive configuration values handled?
A: Use environment variables for sensitive data. The configuration system never logs or exposes sensitive values.

### Q: What happens if required configuration is missing?
A: Pydantic validation raises descriptive errors indicating which fields are missing and their expected format.

### Q: Can configuration be reloaded at runtime?
A: Currently no. Configuration is loaded at startup. Restart the application to pick up configuration changes.

### Q: How do I add custom configuration fields?
A: Extend the `CyRISSettings` class and add fields with appropriate Pydantic validation. Update the parser if needed.

## Related File List

### Core Configuration
- `/home/ubuntu/cyris/src/cyris/config/settings.py` - Pydantic-based configuration model
- `/home/ubuntu/cyris/src/cyris/config/parser.py` - Multi-format configuration parser
- `/home/ubuntu/cyris/src/cyris/config/__init__.py` - Configuration module exports

### Configuration Files
- `/home/ubuntu/cyris/config.yml` - Main system configuration (YAML format)
- `/home/ubuntu/cyris/CONFIG` - Legacy configuration (INI format)
- `/home/ubuntu/cyris/.env` - Environment variable configuration

### Configuration Tests
- `/home/ubuntu/cyris/tests/unit/test_config_parser.py` - Configuration parsing tests
- `/home/ubuntu/cyris/tests/unit/test_settings_validation.py` - Settings validation tests
- `/home/ubuntu/cyris/tests/integration/test_config_integration.py` - Configuration integration tests

### Example Configurations
- `/home/ubuntu/cyris/examples/*.yml` - Example YAML range descriptions
- Configuration templates in documentation
- Environment-specific configuration examples

### Integration Points
- Used by `/home/ubuntu/cyris/src/cyris/cli/main.py` for CLI configuration
- Integrated with `/home/ubuntu/cyris/src/cyris/services/orchestrator.py` for service configuration
- Referenced by all modules requiring system configuration

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Config module documentation with multi-format parsing coverage
- **[VALIDATION]** Documented Pydantic-based validation strategy and error handling approach
- **[COMPATIBILITY]** Outlined legacy INI to modern YAML configuration migration path