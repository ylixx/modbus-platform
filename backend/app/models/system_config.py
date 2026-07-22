"""System config model — key-value store for runtime settings."""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(Text, default="")
    description = Column(Text, default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
