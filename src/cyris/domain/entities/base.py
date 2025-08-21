"""
Base Entity Class
"""
from abc import ABC
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class Entity(BaseModel, ABC):
    """Base Entity Class"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    model_config = {
        # Allow any type (backwards compatible)
        "arbitrary_types_allowed": True,
        # Use enumeration values
        "use_enum_values": True
    }


class ValueObject(BaseModel, ABC):
    """Value Object Base Class"""
    
    model_config = {
        # Value objects are immutable
        "frozen": True,
        "arbitrary_types_allowed": True
    }