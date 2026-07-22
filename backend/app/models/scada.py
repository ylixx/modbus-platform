"""SCADA page and custom widget models."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from app.core.database import Base


class ScadaPage(Base):
    __tablename__ = "scada_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    width = Column(Integer, default=1920)
    height = Column(Integer, default=1080)
    background = Column(String(32), default="#1a1a2e")
    config_json = Column(Text, default="[]")
    device_ids = Column(Text, default="[]")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomWidget(Base):
    """User-uploaded custom SVG/PNG widget."""
    __tablename__ = "custom_widgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    category = Column(String(32), default="custom")
    description = Column(Text, default="")

    # Widget source
    source_type = Column(String(10), nullable=False)   # svg | png | fabric
    source_data = Column(Text, nullable=False)          # SVG string / base64 PNG / fabric JSON

    # Thumbnail (base64 PNG)
    thumbnail = Column(Text, default="")

    # Default size
    default_width = Column(Integer, default=100)
    default_height = Column(Integer, default=100)

    # Bindable fields (JSON array)
    bindable = Column(Text, default='["text","value","state"]')

    # Fabric.js template (JSON) — for complex widgets with parts
    fabric_json = Column(Text, default="")

    enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
