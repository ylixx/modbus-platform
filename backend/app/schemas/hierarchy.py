"""Hierarchy config schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class HierarchyLevel(BaseModel):
    key: str                          # unique key
    label: str                        # display name
    field: str                        # device field or special
    icon: str = ""                    # emoji icon


class HierarchyConfigCreate(BaseModel):
    name: str
    description: str = ""
    levels: List[HierarchyLevel]
    is_default: bool = False


class HierarchyConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    levels: Optional[List[HierarchyLevel]] = None
    is_default: Optional[bool] = None


class HierarchyConfigOut(BaseModel):
    id: int
    name: str
    description: str
    levels: List[HierarchyLevel]
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
