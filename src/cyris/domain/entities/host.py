"""
Host Entity Module
"""
from typing import Optional, List, Union
from pydantic import Field, field_validator
import ipaddress
import re

from .base import Entity


class Host(Entity):
    """
    Host Entity
    Represents physical or virtual host configuration information
    """
    
    host_id: str = Field(..., description="Host unique identifier")
    mgmt_addr: str = Field(..., description="Management address", json_schema_extra={"format": "hostname-or-ip"})
    virbr_addr: str = Field(..., description="Virtual bridge address", json_schema_extra={"format": "hostname-or-ip"})
    account: str = Field(..., description="Host account name")
    
    @field_validator('mgmt_addr', 'virbr_addr', mode='before')
    @classmethod
    def validate_address(cls, v):
        """Validate address is not empty"""
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise ValueError("Address cannot be empty")
        return v.strip()
    
    def get_host_id(self) -> str:
        """Get host ID"""
        return self.host_id
    
    def get_mgmt_addr(self) -> str:
        """Get management address"""
        return self.mgmt_addr
    
    def get_virbr_addr(self) -> str:
        """Get virtual bridge address"""
        return self.virbr_addr
    
    def get_account(self) -> str:
        """Get account name"""
        return self.account
    
    def __str__(self) -> str:
        return (f"Host(id={self.host_id}, mgmt_addr={self.mgmt_addr}, "
                f"virbr_addr={self.virbr_addr}, account={self.account})")


class HostBuilder:
    """Host Builder"""
    
    def __init__(self):
        self._host_id: Optional[str] = None
        self._mgmt_addr: Optional[str] = None
        self._virbr_addr: Optional[str] = None
        self._account: Optional[str] = None
    
    def with_host_id(self, host_id: str) -> 'HostBuilder':
        self._host_id = host_id
        return self
    
    def with_mgmt_addr(self, mgmt_addr: str) -> 'HostBuilder':
        self._mgmt_addr = mgmt_addr
        return self
    
    def with_virbr_addr(self, virbr_addr: str) -> 'HostBuilder':
        self._virbr_addr = virbr_addr
        return self
    
    def with_account(self, account: str) -> 'HostBuilder':
        self._account = account
        return self
    
    def build(self) -> Host:
        """Build host instance"""
        if not all([self._host_id, self._mgmt_addr, self._virbr_addr, self._account]):
            raise ValueError("Missing required fields for Host")
        
        return Host(
            host_id=self._host_id,
            mgmt_addr=self._mgmt_addr,
            virbr_addr=self._virbr_addr,
            account=self._account
        )