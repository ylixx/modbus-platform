"""Custom hierarchy configuration model.

Allows users to define their own tree structure for device grouping.
Example hierarchies:
  - 厂级 → 区级 → 班级 → 设备
  - 区域 → 楼栋 → 楼层 → 设备
  - 客户 → 站点 → 设备
  - 项目 → 模块 → 设备

Each level maps to a device field or a free-text tag.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.core.database import Base


class HierarchyConfig(Base):
    __tablename__ = "hierarchy_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)    # config name, e.g. "默认"
    description = Column(Text, default="")
    levels_json = Column(Text, nullable=False)                 # JSON array of level definitions
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# levels_json example:
# [
#   {"key": "factory",         "label": "厂级",   "field": "factory",        "icon": "🏭"},
#   {"key": "workshop",        "label": "区级",   "field": "workshop",       "icon": "🏢"},
#   {"key": "production_line", "label": "班级",   "field": "production_line","icon": "🔧"},
#   {"key": "device",          "label": "设备",   "field": "_device",        "icon": "📡"}
# ]
#
# field mapping:
#   - "factory", "workshop", "production_line", "installation" → Device model columns
#   - "group" → DeviceGroup name
#   - "protocol" → Device protocol type
#   - "status" → Device status
#   - "tag:<tag_name>" → Match by a specific tag's current value (future)
#   - "_device" → Device leaf node (always last)
