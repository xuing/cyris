"""
System Configuration Settings Module
Uses Pydantic for configuration validation and management
"""
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class CyRISSettings(BaseSettings):
    """CyRIS system configuration"""
    
    # Core path configuration
    cyris_path: Path = Field(
        default=Path.cwd(),
        description="Absolute path to CyRIS installation directory"
    )
    
    cyber_range_dir: Path = Field(
        default=Path.cwd() / "cyber_range",
        description="Directory for cyber range instance storage"
    )
    
    # Gateway configuration
    gw_mode: bool = Field(
        default=False,
        description="Whether to enable gateway mode"
    )
    
    gw_account: Optional[str] = Field(
        default=None,
        description="Gateway account name"
    )
    
    gw_mgmt_addr: Optional[str] = Field(
        default=None,
        description="Gateway management address"
    )
    
    gw_inside_addr: Optional[str] = Field(
        default=None,
        description="Gateway internal address"
    )
    
    user_email: Optional[str] = Field(
        default=None,
        description="User email address"
    )
    
    @field_validator('cyris_path', 'cyber_range_dir')
    @classmethod
    def ensure_absolute_path(cls, v):
        """Ensure path is absolute"""
        if not v.is_absolute():
            v = v.resolve()
        return v
    
    @field_validator('cyber_range_dir')
    @classmethod
    def ensure_cyber_range_dir_exists(cls, v):
        """Ensure cyber range directory exists"""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    class Config:
        env_prefix = "CYRIS_"
        case_sensitive = False