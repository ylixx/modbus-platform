"""User schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    phone: str = ""
    email: str = ""
    role: str = "operator"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    phone: str
    email: str
    role: str
    is_active: bool
    permissions: List[str] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
