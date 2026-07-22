"""Operation audit log model."""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(64), default="")
    action = Column(String(64), nullable=False, index=True)   # e.g. device.create, alarm.acknowledge
    resource_type = Column(String(32), default="")             # device / tag / alarm / sms / user
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(256), default="")
    detail = Column(Text, default="")                          # JSON detail of change
    ip_address = Column(String(64), default="")
    created_at = Column(DateTime, server_default=func.now(), index=True)
