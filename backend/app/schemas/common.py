"""Common response schemas."""
from pydantic import BaseModel
from typing import Optional, Any, Generic, TypeVar

T = TypeVar("T")


class ResponseModel(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class PageResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    total: int = 0
    page: int = 1
    page_size: int = 30
    data: list[T] = []
