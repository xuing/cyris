"""
Virtual Machine Entity Module
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path
import re
from pydantic import Field, field_validator, model_validator

from .base import Entity


class BaseVMType(str, Enum):
    """Base Virtual Machine Type"""
    KVM = "kvm"
    AWS = "aws"
    DOCKER = "docker"
    KVM_AUTO = "kvm-auto"


class OSType(str, Enum):
    """Operating system type"""
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
    Virtual Machine Entity
    Represents virtual machine configuration information
    """
    
    guest_id: str = Field(..., description="Virtual machine unique identifier")
    ip_addr: Optional[str] = Field(default=None, description="IP address for the VM")
    basevm_addr: Optional[str] = Field(default=None, description="Base virtual machine address")
    root_passwd: Optional[str] = Field(default=None, description="Root password")
    basevm_host: Optional[str] = Field(default=None, description="Host where base virtual machine is located")
    basevm_config_file: Optional[str] = Field(default=None, description="Base virtual machine configuration file path")
    basevm_os_type: Optional[OSType] = Field(default=None, description="Operating system type")
    basevm_type: BaseVMType = Field(..., description="Virtualization platform type")
    basevm_name: Optional[str] = Field(default=None, description="Base virtual machine name")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Task list")
    
    # kvm-auto specific fields
    image_name: Optional[str] = Field(default=None, description="virt-builder image name")
    vcpus: Optional[int] = Field(default=None, description="Number of virtual CPUs")
    memory: Optional[int] = Field(default=None, description="Memory in MB")
    disk_size: Optional[str] = Field(default=None, description="Disk size (e.g. '20G')")
    
    @property
    def id(self) -> str:
        """Alias for guest_id to support both old and new interfaces"""
        return self.guest_id
    
    @field_validator('basevm_config_file')
    @classmethod
    def validate_config_file_path(cls, v):
        """Validate configuration file path"""
        if v is None:
            return v  # Allow None for kvm-auto type
        path = Path(v)
        # Allow relative paths, but check format
        if not str(path).endswith('.xml') and not str(path).endswith('.json'):
            raise ValueError("Config file must be .xml or .json format")
        return str(path)
    
    @field_validator('disk_size')
    @classmethod
    def validate_disk_size_format(cls, v):
        """Validate disk size format (e.g. '20G', '1024M')"""
        if v is None:
            return v
        if not re.match(r'^\d+[GMK]$', v):
            raise ValueError("Disk size must be in format like '20G', '1024M', '512K'")
        return v
    
    @model_validator(mode='after')
    def validate_kvm_auto_requirements(self):
        """Validate requirements based on basevm_type"""
        # For kvm-auto, certain fields are required
        if self.basevm_type == BaseVMType.KVM_AUTO:
            required_fields = ['image_name', 'vcpus', 'memory', 'disk_size']
            missing = [f for f in required_fields if not getattr(self, f)]
            if missing:
                raise ValueError(f"kvm-auto requires fields: {missing}")
            
            # Auto-derive basevm_os_type from image_name if not provided
            if not self.basevm_os_type:
                self.basevm_os_type = self._derive_os_type_from_image(self.image_name)
        
        # For non kvm-auto, traditional fields are required
        else:
            if not self.basevm_host:
                raise ValueError("basevm_host is required for non kvm-auto types")
            if not self.basevm_config_file:
                raise ValueError("basevm_config_file is required for non kvm-auto types")
            if not self.basevm_os_type:
                raise ValueError("basevm_os_type is required for non kvm-auto types")
        
        return self
    
    def _derive_os_type_from_image(self, image_name: str) -> OSType:
        """Derive OS type from virt-builder image name"""
        image_to_os_mapping = {
            'ubuntu-20.04': OSType.UBUNTU_20,
            'ubuntu-18.04': OSType.UBUNTU_18,
            'ubuntu-16.04': OSType.UBUNTU_16,
            'ubuntu-22.04': OSType.UBUNTU,
            'centos-7': OSType.CENTOS,
            'centos-8': OSType.CENTOS,
            'fedora-38': OSType.CENTOS,
            'debian-11': OSType.UBUNTU,  # Treat debian as ubuntu-like
        }
        
        return image_to_os_mapping.get(image_name, OSType.UBUNTU)  # Default to ubuntu
    
    def get_guest_id(self) -> str:
        """Get virtual machine ID"""
        return self.guest_id
    
    def get_basevm_addr(self) -> Optional[str]:
        """Get base virtual machine address"""
        return self.basevm_addr
    
    def set_basevm_addr(self, addr: str) -> None:
        """Set base virtual machine address"""
        self.basevm_addr = addr
    
    def get_root_passwd(self) -> Optional[str]:
        """Get root password"""
        return self.root_passwd
    
    def set_root_passwd(self, passwd: str) -> None:
        """Set root password"""
        self.root_passwd = passwd
    
    def get_basevm_host(self) -> Optional[str]:
        """Get base virtual machine host"""
        return self.basevm_host
    
    def get_basevm_config_file(self) -> Optional[str]:
        """Get configuration file path"""
        return self.basevm_config_file
    
    def get_basevm_type(self) -> BaseVMType:
        """Get virtualization platform type"""
        return self.basevm_type
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        """Get task list"""
        return self.tasks
    
    def add_task(self, task: Dict[str, Any]) -> None:
        """Add task"""
        self.tasks.append(task)
    
    def __str__(self) -> str:
        return (f"Guest(id={self.guest_id}, type={self.basevm_type}, "
                f"os={self.basevm_os_type}, host={self.basevm_host})")


class GuestBuilder:
    """Virtual Machine Builder"""
    
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
        
        # kvm-auto specific fields
        self._image_name: Optional[str] = None
        self._vcpus: Optional[int] = None
        self._memory: Optional[int] = None
        self._disk_size: Optional[str] = None
    
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
    
    def with_image_name(self, image_name: str) -> 'GuestBuilder':
        self._image_name = image_name
        return self
    
    def with_vcpus(self, vcpus: int) -> 'GuestBuilder':
        self._vcpus = vcpus
        return self
    
    def with_memory(self, memory: int) -> 'GuestBuilder':
        self._memory = memory
        return self
    
    def with_disk_size(self, disk_size: str) -> 'GuestBuilder':
        self._disk_size = disk_size
        return self
    
    def build(self) -> Guest:
        """Build virtual machine instance"""
        # Basic validation - guest_id and basevm_type are always required
        if not self._guest_id or not self._basevm_type:
            raise ValueError("guest_id and basevm_type are required")
        
        # Additional validation will be done by the Guest model validators
        return Guest(
            guest_id=self._guest_id,
            basevm_addr=self._basevm_addr,
            root_passwd=self._root_passwd,
            basevm_host=self._basevm_host,
            basevm_config_file=self._basevm_config_file,
            basevm_os_type=self._basevm_os_type,
            basevm_type=self._basevm_type,
            basevm_name=self._basevm_name,
            tasks=self._tasks.copy(),
            # kvm-auto fields
            image_name=self._image_name,
            vcpus=self._vcpus,
            memory=self._memory,
            disk_size=self._disk_size
        )