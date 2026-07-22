"""User model."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    display_name = Column(String(128), default="")
    phone = Column(String(20), default="")
    email = Column(String(128), default="")
    role = Column(String(20), default="operator")  # legacy field, kept for backward compat
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    roles = relationship("UserRole", back_populates="user", cascade="all,delete-orphan")
