import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from alloy.models.auth_schemas import RoleEnum, StatusEnum

PHONE_REGEX = re.compile(r"^\+?[0-9\s\-\(\)]{10,18}$")

class ProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name (First and Last name) — required field")
    phone: Optional[str] = Field(None, description="Phone number in the format +380XXXXXXXXX")
    description: Optional[str] = Field(None, max_length=1000, description="Bio description (skills, experience, motivation)")

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            if not PHONE_REGEX.match(v.strip()):
                raise ValueError("Invalid phone number format")
            return v.strip()
        return None

class ProfileReviewItem(BaseModel):
    id: str
    event_id: str
    author_id: str
    author_name: str = Field(..., description="Name or organization title of the review author")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="Review text")
    created_at: datetime

class MyTaskHistoryItem(BaseModel):
    application_id: str
    event_id: str
    event_title: str
    event_status: str
    application_status: str = Field(..., description="Application status: Pending, Approved, Rejected, Withdrawn")
    can_withdraw: bool = Field(
        ...,
        description="Availability of the 'Withdraw application' button"
    )
    applied_at: datetime

class PublicProfileResponse(BaseModel):
    id: str
    role: RoleEnum
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    rating: float = 0.0
    reviews: List[ProfileReviewItem] = []

class MyProfileResponse(PublicProfileResponse):
    email: EmailStr
    phone: Optional[str] = None
    status: StatusEnum
    is_email_verified: bool = False
    email_notifications_enabled: bool = True
    my_tasks: List[MyTaskHistoryItem] = []
