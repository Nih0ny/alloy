from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CategoryCreateUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, description="Category name (e.g., 'Ecology', 'Animals')")

    @field_validator("name")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Category name cannot be empty")
        return cleaned


class CategoryPublicResponse(BaseModel):
    id: str
    name: str


class CategoryAdminResponse(CategoryPublicResponse):
    active_events_count: int = Field(
        0,
        description="Number of active events linked to the category"
    )
    total_events_count: int = Field(
        0,
        description="Total number of all events (to check if complete deletion is possible)"
    )
    is_archived: bool = Field(
        False,
        description="Hidden (archived) status if the category was deleted while having events"
    )
    created_at: datetime
    updated_at: Optional[datetime] = None


class CategoryDeleteResponse(BaseModel):
    id: str
    name: str
    action: str = Field(..., description="'deleted' or 'archived'")
    message: str
