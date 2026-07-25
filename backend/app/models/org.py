"""Organization structure models.

OrgNode      ← 组织架构节点（灵活层级树：厂级/区级/班组级/位置，允许任意深度与跳级）
RoleOrgScope ← 角色-组织范围关联（角色 data_scope='org' 时生效，命中节点含其整个子树）

设备通过 Device.org_node_id 归属到任意组织节点。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class OrgNode(Base):
    """组织架构节点（任意深度树）。"""
    __tablename__ = "org_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    # 节点类型（可选标识，不强制层级顺序）: factory | area | team | location | other
    node_type = Column(String(20), default="other")
    parent_id = Column(Integer, ForeignKey("org_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    description = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    children = relationship(
        "OrgNode",
        backref="parent",
        remote_side=[id],
        lazy="select",
    )


class RoleOrgScope(Base):
    """角色的组织数据范围：角色可见这些节点及其整个子树下的设备数据。"""
    __tablename__ = "role_org_scopes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    org_node_id = Column(Integer, ForeignKey("org_nodes.id", ondelete="CASCADE"), nullable=False, index=True)

    role = relationship("Role", back_populates="org_scopes")
    org_node = relationship("OrgNode")
