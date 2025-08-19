"""
基础实体类
"""
from abc import ABC
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class Entity(BaseModel, ABC):
    """基础实体类"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    model_config = {
        # 允许任意类型（向后兼容）
        "arbitrary_types_allowed": True,
        # 使用枚举值
        "use_enum_values": True
    }


class ValueObject(BaseModel, ABC):
    """值对象基类"""
    
    model_config = {
        # 值对象不可变
        "frozen": True,
        "arbitrary_types_allowed": True
    }