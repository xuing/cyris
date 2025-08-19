"""
系统配置设置模块
使用Pydantic进行配置验证和管理
"""
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class CyRISSettings(BaseSettings):
    """CyRIS系统配置"""
    
    # 核心路径配置
    cyris_path: Path = Field(
        default=Path.cwd(),
        description="CyRIS安装目录的绝对路径"
    )
    
    cyber_range_dir: Path = Field(
        default=Path.cwd() / "cyber_range",
        description="网络靶场实例存储目录"
    )
    
    # 网关配置
    gw_mode: bool = Field(
        default=False,
        description="是否启用网关模式"
    )
    
    gw_account: Optional[str] = Field(
        default=None,
        description="网关账户名"
    )
    
    gw_mgmt_addr: Optional[str] = Field(
        default=None,
        description="网关管理地址"
    )
    
    gw_inside_addr: Optional[str] = Field(
        default=None,
        description="网关内部地址"
    )
    
    user_email: Optional[str] = Field(
        default=None,
        description="用户邮箱地址"
    )
    
    @field_validator('cyris_path', 'cyber_range_dir')
    @classmethod
    def ensure_absolute_path(cls, v):
        """确保路径是绝对路径"""
        if not v.is_absolute():
            v = v.resolve()
        return v
    
    @field_validator('cyber_range_dir')
    @classmethod
    def ensure_cyber_range_dir_exists(cls, v):
        """确保网络靶场目录存在"""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    model_config = {
        "env_prefix": "CYRIS_",
        "case_sensitive": False
    }