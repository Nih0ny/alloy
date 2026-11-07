from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from alloy.models.auth_schemas import RoleEnum, StatusEnum

class ComplaintTargetTypeEnum(str, Enum):
    user = "User"
    event = "Event"
    comment = "Comment"

class ComplaintStatusEnum(str, Enum):
    pending = "Pending"
    rejected = "Rejected"
    resolved = "Resolved"

class ComplaintCreate(BaseModel):
    target_type: ComplaintTargetTypeEnum = Field(..., description="Target of complaint: User, Event, or Comment")
    target_id: str = Field(..., description="ID of the user, event, or comment")
    violation_category: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Violation category (e.g., Fraud, Insults, Spam)"
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Text description of the violation"
    )

    @field_validator("violation_category", "description")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

class ComplaintRejectRequest(BaseModel):
    admin_note: Optional[str] = Field(None, max_length=500)

class UserBlockRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Mandatory blocking reason that will be sent to the user via email"
    )
    complaint_id: Optional[str] = Field(
        None,
        description="Optional ID of the complaint upon which the block is based"
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("You must specify a reason for blocking")
        return cleaned

class ComplaintResponse(BaseModel):
    id: str
    reporter_id: str
    reporter_name: str = Field(..., description="Author of the complaint")
    target_type: ComplaintTargetTypeEnum = Field(..., description="Type of the complaint target")
    target_id: str
    target_summary: str = Field(..., description="Event name, comment text, or full name of the reported user")
    accused_user_id: Optional[str] = Field(None, description="ID of the content owner / violator for quick blocking")
    accused_user_name: Optional[str] = None
    violation_category: str
    description: str = Field(..., description="Complaint text / violation description")
    status: ComplaintStatusEnum
    admin_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

class AdminUserRegistryItem(BaseModel):
    id: str
    email: EmailStr
    full_name: str = Field(..., description="Full Name / Name")
    role: RoleEnum = Field(..., description="Role: Volunteer or Organizer")
    status: StatusEnum = Field(..., description="Account status: Active or Blocked")
    rating: float = 0.0
    block_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None
