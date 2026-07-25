"""RBAC + Data Scope permission models.

Structure:
  Permission  ← 权限点 (device.read, alarm.ack, sms.send, ...)
  Role        ← 角色 (admin, operator, engineer, viewer)
  RolePermission ← 角色-权限关联
  UserRole    ← 用户-角色关联 + 数据范围

Data Scope types:
  all         - 全部数据
  factory     - 指定厂级
  workshop    - 指定区级
  self        - 仅自己创建的
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Permission(Base):
    """Permission point definition."""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)  # e.g. device.read
    name = Column(String(128), nullable=False)                           # e.g. 查看设备
    module = Column(String(32), nullable=False, index=True)              # e.g. device
    description = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class Role(Base):
    """Role definition."""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)  # e.g. admin
    name = Column(String(64), nullable=False)                            # e.g. 系统管理员
    description = Column(Text, default="")
    is_system = Column(Boolean, default=False)                           # system roles can't be deleted
    # 组织数据范围: all=全部数据 | org=按 role_org_scopes 绑定的组织子树过滤
    data_scope = Column(String(20), default="all")
    created_at = Column(DateTime, server_default=func.now())

    permissions = relationship("RolePermission", back_populates="role", cascade="all,delete-orphan")
    users = relationship("UserRole", back_populates="role")
    org_scopes = relationship("RoleOrgScope", back_populates="role", cascade="all,delete-orphan")


class RolePermission(Base):
    """Role-Permission mapping."""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission")


class UserRole(Base):
    """User-Role mapping with data scope."""
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Data scope
    data_scope = Column(String(20), default="all")  # all | factory | workshop | self
    scope_values = Column(Text, default="")          # JSON array: ["区级A", "区级B"]

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")
