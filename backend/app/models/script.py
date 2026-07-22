"""Script model — user-defined data processing algorithms."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.core.database import Base


class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, default="")
    language = Column(String(20), default="python")  # python

    # The script source code
    # Must define: def process(raw_value, history, tag_config, context) -> float | dict
    code = Column(Text, nullable=False)

    # Default parameters (JSON) — accessible inside script as tag_config['params']
    default_params = Column(Text, default="{}")

    # Execution limits
    timeout_ms = Column(Integer, default=1000)  # max execution time in ms
    max_history = Column(Integer, default=100)  # max history values passed to script

    # Metadata
    is_template = Column(Boolean, default=False)  # system template, can't be deleted
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
