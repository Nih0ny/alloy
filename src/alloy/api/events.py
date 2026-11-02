from typing import List, Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, status

from alloy.models.event_schemas import (
    EventCreate,
    EventUpdate,
    EventStatusUpdate,
    EventModerationRequest,
    EventCardResponse,
    EventDetailResponse,
)
from alloy.services.event_service import EventService
from alloy.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_event_service,
)

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


@router.get("", response_model=List[EventCardResponse])
async def list_public_events(
    search: Optional[str] = Query(None, description="Search by keywords in title or description"),
    categories: Optional[List[str]] = Query(None, description="Filter by category list"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.get_public_events(search, categories, skip, limit)


@router.get("/my", response_model=List[EventCardResponse])
async def get_my_events(
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.get_my_organized_events(current_user)


@router.get("/moderation/pending", response_model=List[EventDetailResponse])
async def get_pending_moderation_events(
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.get_pending_events_for_admin(current_user)


@router.post("", response_model=EventDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.create_event(event_in, current_user)


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event_details(
    event_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.get_event_details(event_id, current_user)


@router.put("/{event_id}", response_model=EventDetailResponse)
async def update_event(
    event_id: str,
    event_in: EventUpdate,
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.update_event(event_id, event_in, current_user)


@router.patch("/{event_id}/status", response_model=EventDetailResponse)
async def change_event_status(
    event_id: str,
    status_in: EventStatusUpdate,
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.change_event_status(event_id, status_in, current_user)


@router.post("/{event_id}/photos", response_model=EventDetailResponse)
async def upload_event_photos(
    event_id: str,
    files: List[UploadFile] = File(..., description="Event photos (JPG, PNG)"),
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.upload_event_photos(event_id, files, current_user)


@router.patch("/{event_id}/moderation", response_model=EventDetailResponse)
async def moderate_event(
    event_id: str,
    mod_in: EventModerationRequest,
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    return await event_service.moderate_event(event_id, mod_in, current_user)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service)
):
    await event_service.delete_event(event_id, current_user)
