from typing import List
from fastapi import APIRouter, Depends, status

from alloy.models.review_schemas import (
    OrganizerReviewVolunteerCreate,
    VolunteerReviewOrganizerCreate,
    ReviewResponse,
    ReviewTargetInfoResponse,
)
from alloy.services.review_service import ReviewService
from alloy.dependencies import get_current_user, get_review_service

router = APIRouter(prefix="/api/v1", tags=["Reviews"])

@router.get(
    "/events/{event_id}/reviews/form-info/{target_user_id}",
    response_model=ReviewTargetInfoResponse
)
async def get_review_form_info(
    event_id: str,
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service)
):
    return await review_service.get_review_form_context(event_id, target_user_id, current_user)

@router.post(
    "/events/{event_id}/reviews/volunteer",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED
)
async def review_volunteer(
    event_id: str,
    review_in: OrganizerReviewVolunteerCreate,
    current_user: dict = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service)
):
    return await review_service.review_volunteer_by_organizer(event_id, review_in, current_user)

@router.post(
    "/events/{event_id}/reviews/organizer",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED
)
async def review_organizer(
    event_id: str,
    review_in: VolunteerReviewOrganizerCreate,
    current_user: dict = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service)
):
    return await review_service.review_organizer_by_volunteer(event_id, review_in, current_user)

@router.get(
    "/events/{event_id}/reviews",
    response_model=List[ReviewResponse]
)
async def list_event_reviews(
    event_id: str,
    review_service: ReviewService = Depends(get_review_service)
):
    return await review_service.get_event_reviews(event_id)
