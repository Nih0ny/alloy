from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class ApplicationStatusEnum(str, Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"
    withdrawn = "Withdrawn"


class OrganizerDecisionEnum(str, Enum):
    approved = "Approved"
    rejected = "Rejected"


class ApplicationCreate(BaseModel):
    motivation_letter: Optional[str] = Field(
        None,
        max_length=1000,
        description="Cover message / motivation (optional)"
    )
    agreed_to_share_contacts: bool = Field(
        ...,
        description="Mandatory consent to share contact details with the Organizer upon approval"
    )

    @model_validator(mode="after")
    def check_contacts_consent(self) -> "ApplicationCreate":
        if not self.agreed_to_share_contacts:
            raise ValueError(
                "Consent to share contact details with the Organizer must be provided"
            )
        return self


class ApplicationReviewRequest(BaseModel):
    status: OrganizerDecisionEnum
    rejection_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional rejection reason when declining the application"
    )


class OrganizerContactsInfo(BaseModel):
    full_name: Optional[str] = None
    email: str
    phone: Optional[str] = None


class VolunteerApplicationResponse(BaseModel):
    id: str
    event_id: str
    event_title: str
    event_date: Optional[datetime] = None
    event_status: str
    volunteer_id: str
    motivation_letter: Optional[str] = None
    status: ApplicationStatusEnum
    rejection_reason: Optional[str] = None
    can_withdraw: bool
    organizer_contacts: Optional[OrganizerContactsInfo] = Field(
        None,
        description="Populated only when the application is 'Approved'"
    )
    created_at: datetime
    updated_at: datetime


class OrganizerApplicantItem(BaseModel):
    application_id: str
    volunteer_id: str
    volunteer_name: str = Field(..., description="Volunteer full name")
    volunteer_avatar_url: Optional[str] = Field(None, description="Volunteer avatar URL")
    volunteer_rating: float = Field(0.0, description="Overall volunteer rating")
    volunteer_phone: Optional[str] = Field(
        None,
        description="Volunteer phone number (revealed to the Organizer upon approval)"
    )
    motivation_letter: Optional[str] = Field(None, description="Cover message")
    status: ApplicationStatusEnum = Field(..., description="Current application status")
    rejection_reason: Optional[str] = None
    created_at: datetime


class EventApplicationsManageResponse(BaseModel):
    event_id: str
    event_title: str = Field(..., description="Event title")
    event_status: str = Field(..., description="Current event status")
    progress_text: str = Field(..., description="Format 'Confirmed: X of Y'")
    volunteer_quota: int
    approved_volunteers_count: int
    applications: List[OrganizerApplicantItem] = Field(..., description="List of submitted applications")
