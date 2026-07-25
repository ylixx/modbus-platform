"""Lab data and pre-aggregated statistics models."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index, func
from app.core.database import Base


class LabData(Base):
    """Manual lab/test data for comparison with automated collection."""
    __tablename__ = "lab_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("device_tags.id", ondelete="SET NULL"), nullable=True, index=True)

    lab_name = Column(String(128), nullable=False)       # 化验项目名（如 COD、氨氮、pH）
    lab_value = Column(Float, nullable=False)             # 化验值
    unit = Column(String(32), default="")                 # 单位
    sample_time = Column(DateTime, nullable=False, index=True)  # 采样时间
    operator = Column(String(64), default="")             # 化验员
    remark = Column(Text, default="")

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_lab_device_tag_time", "device_id", "tag_id", "sample_time"),
    )


class TagAggregate(Base):
    """Pre-aggregated statistics for fast querying."""
    __tablename__ = "tag_aggregate"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    tag_name = Column(String(128), default="")

    granularity = Column(Integer, nullable=False)         # 聚合粒度（秒）: 60, 300, 900, 3600, 86400, ...
    bucket_time = Column(DateTime, nullable=False, index=True)  # 时间桶起始时间

    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    avg_value = Column(Float, nullable=True)
    count = Column(Integer, default=0)
    first_value = Column(Float, nullable=True)
    last_value = Column(Float, nullable=True)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_agg_device_tag_gran_bucket", "device_id", "tag_id", "granularity", "bucket_time", unique=True),
    )
