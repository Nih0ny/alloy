from fastapi import APIRouter, Depends, Query

from alloy.models.notification_schemas import NotificationResponse, NotificationListResponse
from alloy.services.notification_service import NotificationService
from alloy.dependencies import get_current_user, get_notification_service

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

@router.get("", response_model=NotificationListResponse)
async def list_my_notifications(
    unread_only: bool = Query(False, description="Show only unread notifications"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    notif_service: NotificationService = Depends(get_notification_service)
):
    return await notif_service.get_my_notifications(current_user, unread_only, skip, limit)

@router.patch("/read-all")
async def mark_all_notifications_as_read(
    current_user: dict = Depends(get_current_user),
    notif_service: NotificationService = Depends(get_notification_service)
):
    return await notif_service.mark_all_read(current_user)

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_single_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    notif_service: NotificationService = Depends(get_notification_service)
):
    return await notif_service.mark_notification_read(notification_id, current_user)
