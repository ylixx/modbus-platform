"""Tag history model for time-series data."""
from sqlalchemy import Column, Integer, String, Float, DateTime, func, Index
from app.core.database import Base


class TagHistory(Base):
    """Stores historical values for device tags.

    For high-volume production, consider partitioning by time
    or using TimescaleDB / TDengine.
    """
    __tablename__ = "tag_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    tag_name = Column(String(128), nullable=False)

    value = Column(Float, nullable=True)
    raw_value = Column(String(256), default="")  # original raw read
    quality = Column(String(20), default="good")  # good / bad / uncertain

    recorded_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_history_device_tag_time", "device_id", "tag_id", "recorded_at"),
    )
