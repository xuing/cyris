"""
虚拟机实体模块
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path
from pydantic import Field, field_validator

from .base import Entity


class BaseVMType(str, Enum):
    """基础虚拟机类型"""
    KVM = "kvm"
    AWS = "aws"
    DOCKER = "docker"


class OSType(str, Enum):
    """操作系统类型"""
    UBUNTU = "ubuntu"
    UBUNTU_16 = "ubuntu_16"
    UBUNTU_18 = "ubuntu_18"
    UBUNTU_20 = "ubuntu_20"
    CENTOS = "centos"
    WINDOWS_7 = "windows.7"
    WINDOWS_8_1 = "windows.8.1"
    WINDOWS_10 = "windows.10"
    AMAZON_LINUX = "amazon_linux"
    AMAZON_LINUX2 = "amazon_linux2"
    RED_HAT = "red_hat"


class Guest(Entity):
    """
    虚拟机实体
    表示虚拟机的配置信息
    """
    
    guest_id: str = Field(..., description="虚拟机唯一标识符")
    basevm_addr: Optional[str] = Field(default=None, description="基础虚拟机地址")
    root_passwd: Optional[str] = Field(default=None, description="Root密码")
    basevm_host: str = Field(..., description="基础虚拟机所在主机")
    basevm_config_file: str = Field(..., description="基础虚拟机配置文件路径")
    basevm_os_type: OSType = Field(..., description="操作系统类型")
    basevm_type: BaseVMType = Field(..., description="虚拟化平台类型")
    basevm_name: Optional[str] = Field(default=None, description="基础虚拟机名称")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="任务列表")
    
    @field_validator('basevm_config_file')
    @classmethod
    def validate_config_file_path(cls, v):
        """验证配置文件路径"""
        path = Path(v)
        # 允许相对路径，但检查格式
        if not str(path).endswith('.xml') and not str(path).endswith('.json'):
            raise ValueError("Config file must be .xml or .json format")
        return str(path)
    
    def get_guest_id(self) -> str:
        """获取虚拟机ID"""
        return self.guest_id
    
    def get_basevm_addr(self) -> Optional[str]:
        """获取基础虚拟机地址"""
        return self.basevm_addr
    
    def set_basevm_addr(self, addr: str) -> None:
        """设置基础虚拟机地址"""
        self.basevm_addr = addr
    
    def get_root_passwd(self) -> Optional[str]:
        """获取root密码"""
        return self.root_passwd
    
    def set_root_passwd(self, passwd: str) -> None:
        """设置root密码"""
        self.root_passwd = passwd
    
    def get_basevm_host(self) -> str:
        """获取基础虚拟机主机"""
        return self.basevm_host
    
    def get_basevm_config_file(self) -> str:
        """获取配置文件路径"""
        return self.basevm_config_file
    
    def get_basevm_type(self) -> BaseVMType:
        """获取虚拟化平台类型"""
        return self.basevm_type
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        """获取任务列表"""
        return self.tasks
    
    def add_task(self, task: Dict[str, Any]) -> None:
        """添加任务"""
        self.tasks.append(task)
    
    def __str__(self) -> str:
        return (f"Guest(id={self.guest_id}, type={self.basevm_type}, "
                f"os={self.basevm_os_type}, host={self.basevm_host})")


class GuestBuilder:
    """虚拟机构建器"""
    
    def __init__(self):
        self._guest_id: Optional[str] = None
        self._basevm_addr: Optional[str] = None
        self._root_passwd: Optional[str] = None
        self._basevm_host: Optional[str] = None
        self._basevm_config_file: Optional[str] = None
        self._basevm_os_type: Optional[OSType] = None
        self._basevm_type: Optional[BaseVMType] = None
        self._basevm_name: Optional[str] = None
        self._tasks: List[Dict[str, Any]] = []
    
    def with_guest_id(self, guest_id: str) -> 'GuestBuilder':
        self._guest_id = guest_id
        return self
    
    def with_basevm_addr(self, addr: str) -> 'GuestBuilder':
        self._basevm_addr = addr
        return self
    
    def with_root_passwd(self, passwd: str) -> 'GuestBuilder':
        self._root_passwd = passwd
        return self
    
    def with_basevm_host(self, host: str) -> 'GuestBuilder':
        self._basevm_host = host
        return self
    
    def with_basevm_config_file(self, config_file: str) -> 'GuestBuilder':
        self._basevm_config_file = config_file
        return self
    
    def with_basevm_os_type(self, os_type: OSType) -> 'GuestBuilder':
        self._basevm_os_type = os_type
        return self
    
    def with_basevm_type(self, vm_type: BaseVMType) -> 'GuestBuilder':
        self._basevm_type = vm_type
        return self
    
    def with_basevm_name(self, name: str) -> 'GuestBuilder':
        self._basevm_name = name
        return self
    
    def with_task(self, task: Dict[str, Any]) -> 'GuestBuilder':
        self._tasks.append(task)
        return self
    
    def build(self) -> Guest:
        """构建虚拟机实例"""
        required_fields = [
            self._guest_id, self._basevm_host, self._basevm_config_file,
            self._basevm_os_type, self._basevm_type
        ]
        
        if not all(f is not None for f in required_fields):
            raise ValueError("Missing required fields for Guest")
        
        return Guest(
            guest_id=self._guest_id,
            basevm_addr=self._basevm_addr,
            root_passwd=self._root_passwd,
            basevm_host=self._basevm_host,
            basevm_config_file=self._basevm_config_file,
            basevm_os_type=self._basevm_os_type,
            basevm_type=self._basevm_type,
            basevm_name=self._basevm_name,
            tasks=self._tasks.copy()
        )