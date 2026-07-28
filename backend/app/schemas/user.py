"""User schemas."""
import re
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


# 密码复杂度规则：至少 8 位，包含字母和数字
PASSWORD_MIN_LENGTH = 8
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')


def validate_password_complexity(password: str, field_name: str = "密码") -> str:
    """校验密码复杂度：至少 8 位，必须包含字母和数字。"""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"{field_name}长度至少 {PASSWORD_MIN_LENGTH} 位")
    if not re.search(r'[a-zA-Z]', password):
        raise ValueError(f"{field_name}必须包含至少一个字母")
    if not re.search(r'[0-9]', password):
        raise ValueError(f"{field_name}必须包含至少一个数字")
    return password


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    phone: str = ""
    email: str = ""
    role: str = "operator"

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        v = v.strip()
        if len(v) < USERNAME_MIN_LENGTH:
            raise ValueError(f'用户名长度至少 {USERNAME_MIN_LENGTH} 位')
        if len(v) > USERNAME_MAX_LENGTH:
            raise ValueError(f'用户名长度不能超过 {USERNAME_MAX_LENGTH} 位')
        if not USERNAME_PATTERN.match(v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        return validate_password_complexity(v, "密码")


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


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        return validate_password_complexity(v, "新密码")


class ResetPasswordRequest(BaseModel):
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_reset_password(cls, v):
        return validate_password_complexity(v, "新密码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
