from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ReviewCreateBase(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating on a scale from 1 to 5")
    comment: str = Field(..., min_length=2, max_length=1000, description="Text review regarding the collaboration")

class OrganizerReviewVolunteerCreate(ReviewCreateBase):
    volunteer_id: str = Field(..., description="ID of the verified volunteer being reviewed by the organizer")

class VolunteerReviewOrganizerCreate(ReviewCreateBase):
    pass

class ReviewTargetInfoResponse(BaseModel):
    event_id: str
    event_title: str = Field(..., description="Title of the event during which the collaboration took place")
    reviewee_id: str
    reviewee_name: str = Field(..., description="Full name or organization title of the reviewee")
    reviewee_role: str
    already_reviewed: bool = Field(..., description="Indicates whether the current user has already left a review for this person")
    can_review: bool = Field(..., description="Indicates whether reviewing is allowed at the current stage")

class ReviewResponse(BaseModel):
    id: str
    event_id: str
    event_title: str
    reviewer_id: str
    reviewer_name: str
    reviewee_id: str
    reviewee_name: str
    rating: int
    comment: Optional[str] = None
    reviewee_new_average_rating: float = Field(
        ...,
        description="New recalculated average rating of the reviewed user"
    )
    created_at: datetime
