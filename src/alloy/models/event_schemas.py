from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class ModerationStatusEnum(str, Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"


class EventLifecycleStatusEnum(str, Enum):
    draft = "Pending Moderation"
    open = "Open"
    in_process = "In Process"
    completed = "Completed"
    cancelled = "Cancelled"


class OrganizerAllowedStatusEnum(str, Enum):
    in_process = "In Process"
    completed = "Completed"
    cancelled = "Cancelled"


class GeoLocation(BaseModel):
    address: str = Field(..., min_length=5, description="Physical address of the event")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude (map pin)")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude (map pin)")


class EventCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=150, description="Short title of the initiative")
    description: str = Field(..., min_length=50, description="Detailed description (minimum 50 characters)")
    category_id: Optional[str] = Field(None, description="Category ID or name from reference book")
    event_date: datetime = Field(..., description="Date and time of the event")
    location: GeoLocation
    volunteer_quota: int = Field(..., gt=0, description="Required number of volunteers")


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=150)
    description: Optional[str] = Field(None, min_length=50)
    category_id: Optional[str] = None
    event_date: Optional[datetime] = None
    location: Optional[GeoLocation] = None
    volunteer_quota: Optional[int] = Field(None, gt=0)


class EventStatusUpdate(BaseModel):
    status: OrganizerAllowedStatusEnum


class EventModerationRequest(BaseModel):
    action: ModerationStatusEnum
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection (mandatory if refused)")

    @model_validator(mode="after")
    def check_rejection_reason(self) -> "EventModerationRequest":
        if self.action == ModerationStatusEnum.pending:
            raise ValueError("Cannot change status back to 'Pending'")
        if self.action == ModerationStatusEnum.rejected and (not self.rejection_reason or not self.rejection_reason.strip()):
            raise ValueError("A reason must be provided when rejecting an event")
        return self


class OrganizerShortInfo(BaseModel):
    id: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    rating: float = 0.0


class EventCardResponse(BaseModel):
    id: str
    title: str
    location: GeoLocation
    event_date: datetime
    category_id: Optional[str] = None
    status: EventLifecycleStatusEnum
    moderation_status: ModerationStatusEnum
    volunteer_quota: int
    approved_volunteers_count: int
    progress_text: str  # Format 'Collected X of Y'
    photos: List[str] = []


class EventDetailResponse(EventCardResponse):
    description: str
    organizer: OrganizerShortInfo
    rejection_reason: Optional[str] = None
    created_at: datetime
