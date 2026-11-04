from typing import List
from fastapi import APIRouter, Depends, status

from alloy.models.application_schemas import (
    ApplicationCreate,
    ApplicationReviewRequest,
    VolunteerApplicationResponse,
    EventApplicationsManageResponse,
)
from alloy.services.application_service import ApplicationService
from alloy.dependencies import get_current_user, get_application_service

router = APIRouter(prefix="/api/v1", tags=["Volunteer Applications"])


@router.post(
    "/events/{event_id}/applications",
    response_model=VolunteerApplicationResponse,
    status_code=status.HTTP_201_CREATED
)
async def apply_for_event(
    event_id: str,
    app_in: ApplicationCreate,
    current_user: dict = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    return await app_service.submit_application(event_id, app_in, current_user)


@router.get("/applications/my", response_model=List[VolunteerApplicationResponse])
async def get_my_applications(
    current_user: dict = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    return await app_service.get_my_applications(current_user)


@router.get("/applications/{application_id}", response_model=VolunteerApplicationResponse)
async def get_application_details(
    application_id: str,
    current_user: dict = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    return await app_service.get_application_details(application_id, current_user)


@router.patch(
    "/applications/{application_id}/withdraw",
    response_model=VolunteerApplicationResponse
)
async def withdraw_application(
    application_id: str,
    current_user: dict = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    return await app_service.withdraw_application(application_id, current_user)


@router.get(
    "/events/{event_id}/applications",
    response_model=EventApplicationsManageResponse
)
async def get_event_applications(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    return await app_service.get_event_applications_for_organizer(event_id, current_user)


@router.patch(
    "/applications/{application_id}/review",
    response_model=VolunteerApplicationResponse
)
async def review_volunteer_application(
    application_id: str,
    review_in: ApplicationReviewRequest,
    current_user: dict = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    return await app_service.review_application(application_id, review_in, current_user)
