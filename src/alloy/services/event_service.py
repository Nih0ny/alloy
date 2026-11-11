import os
import uuid
import aiofiles
from datetime import datetime, UTC
from typing import List, Optional
from fastapi import HTTPException, UploadFile, status, File
from bson import ObjectId

from alloy.repositories.event_repository import EventRepository
from alloy.repositories.user_repository import UserRepository
from alloy.models.event_schemas import (
    EventCreate,
    EventUpdate,
    EventStatusUpdate,
    EventModerationRequest,
    ModerationStatusEnum,
    EventLifecycleStatusEnum,
)
from alloy.services.notification_service import NotificationService
from alloy.models.notification_schemas import NotificationTypeEnum
from alloy.models.auth_schemas import RoleEnum

EVENT_PHOTOS_DIR = "uploads/events"
os.makedirs(EVENT_PHOTOS_DIR, exist_ok=True)


class EventService:
    def __init__(self, event_repository: EventRepository, user_repository: UserRepository, notif_service: NotificationService):
        self.event_repository = event_repository
        self.user_repository = user_repository
        self.notif_service = notif_service

    def _format_event_card(self, event: dict) -> dict:
        approved = event.get("approved_volunteers_count", 0)
        quota = event.get("volunteer_quota", 1)
        return {
            "id": str(event["_id"]),
            "title": event["title"],
            "location": event["location"],
            "event_date": event["event_date"],
            "category_id": event.get("category_id"),
            "status": event["status"],
            "moderation_status": event["moderation_status"],
            "volunteer_quota": quota,
            "approved_volunteers_count": approved,
            "progress_text": f"Collected {approved} of {quota}",
            "photos": event.get("photos", [])
        }

    async def _format_event_detail(self, event: dict) -> dict:
        card = self._format_event_card(event)
        organizer_id = event["organizer_id"]
        organizer_user = await self.user_repository.get_user_by_id(organizer_id)

        profile = organizer_user.get("profile", {}) if organizer_user else {}
        organizer_info = {
            "id": organizer_id,
            "full_name": profile.get("full_name") or (organizer_user["email"] if organizer_user else "Unknown"),
            "avatar_url": profile.get("avatar_url"),
            "rating": profile.get("rating", 0.0)
        }

        card.update({
            "description": event["description"],
            "organizer": organizer_info,
            "rejection_reason": event.get("rejection_reason"),
            "created_at": event["created_at"]
        })
        return card

    async def create_event(self, event_in: EventCreate, current_user: dict) -> dict:
        if current_user.get("role") != RoleEnum.organizer.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only users with the 'Organizer' role can create events"
            )

        if event_in.category_id:
            category = await self.event_repository.db["categories"].find_one({
                "$or": [
                    {"_id": ObjectId(event_in.category_id)} if ObjectId.is_valid(event_in.category_id) else {"name": event_in.category_id},
                    {"name": event_in.category_id}
                ],
                "is_archived": False
            })
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The selected category does not exist in the active directory"
                )

        now = datetime.now(UTC)
        event_dict = {
            "title": event_in.title,
            "description": event_in.description,
            "category_id": event_in.category_id,
            "event_date": event_in.event_date,
            "location": event_in.location.model_dump(),
            "volunteer_quota": event_in.volunteer_quota,
            "approved_volunteers_count": 0,
            "photos": [],
            "organizer_id": str(current_user["_id"]),
            "moderation_status": ModerationStatusEnum.pending.value,
            "status": EventLifecycleStatusEnum.draft.value,
            "rejection_reason": None,
            "created_at": now,
            "updated_at": now
        }

        created = await self.event_repository.create_event(event_dict)
        return await self._format_event_detail(created)

    async def get_public_events(
        self,
        search: Optional[str] = None,
        categories: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        events = await self.event_repository.get_public_events(search, categories, skip, limit)
        return [self._format_event_card(e) for e in events]

    async def get_event_details(self, event_id: str, current_user: Optional[dict] = None) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        is_public_open = (
            event.get("status") == EventLifecycleStatusEnum.open.value
            and event.get("moderation_status") == ModerationStatusEnum.approved.value
        )

        if not is_public_open:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This event is not available for unauthorized viewing"
                )
            user_id = str(current_user["_id"])
            is_owner = user_id == event["organizer_id"]
            is_admin = current_user.get("role") == RoleEnum.admin.value

            has_application = await self.event_repository.db["applications"].find_one({
                "event_id": event_id,
                "volunteer_id": user_id
            }) is not None

            if not (is_owner or is_admin or has_application):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to view this event"
                )

        return await self._format_event_detail(event)

    async def get_my_organized_events(self, current_user: dict) -> List[dict]:
        if current_user.get("role") != RoleEnum.organizer.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Available only for Organizers"
            )
        events = await self.event_repository.get_events_by_organizer(str(current_user["_id"]))
        return [self._format_event_card(e) for e in events]

    async def update_event(self, event_id: str, event_in: EventUpdate, current_user: dict) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["organizer_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the organizer of this event")

        if event["status"] in [EventLifecycleStatusEnum.completed.value, EventLifecycleStatusEnum.cancelled.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot edit a completed or cancelled event"
            )

        if event_in.category_id:
            category = await self.event_repository.db["categories"].find_one({
                "$or": [
                    {"_id": ObjectId(event_in.category_id)} if ObjectId.is_valid(event_in.category_id) else {"name": event_in.category_id},
                    {"name": event_in.category_id}
                ],
                "is_archived": False
            })
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The selected category does not exist in the active directory"
                )

        update_data = event_in.model_dump(exclude_unset=True)
        if not update_data:
            return await self._format_event_detail(event)

        approved_count = event.get("approved_volunteers_count", 0)
        if "volunteer_quota" in update_data and update_data["volunteer_quota"] < approved_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The new quota ({update_data['volunteer_quota']}) cannot be less than the number of already approved volunteers ({approved_count})"
            )

        if "location" in update_data and update_data["location"] is not None:
            update_data["location"] = event_in.location.model_dump()

        if approved_count == 0:
            update_data["moderation_status"] = ModerationStatusEnum.pending.value
            update_data["status"] = EventLifecycleStatusEnum.draft.value
            update_data["rejection_reason"] = None

        updated = await self.event_repository.update_event(event_id, update_data)
        return await self._format_event_detail(updated)

    async def change_event_status(
        self, event_id: str, status_in: EventStatusUpdate, current_user: dict
    ) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["organizer_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the author of this event")

        if (
            event["moderation_status"] != ModerationStatusEnum.approved.value
            and status_in.status.value != EventLifecycleStatusEnum.cancelled.value
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot activate an event that has not yet passed Administrator moderation"
            )

        new_status = status_in.status.value

        cursor = self.event_repository.db["applications"].find({
            "event_id": event_id,
            "status": {"$in": ["Pending", "Approved"]}
        })
        related_apps = await cursor.to_list(length=500)
        volunteer_ids = [app["volunteer_id"] for app in related_apps]

        updated = await self.event_repository.update_event(event_id, {"status": new_status})

        if new_status == EventLifecycleStatusEnum.cancelled.value:
            await self.event_repository.cancel_active_applications_for_event(event_id)

        if volunteer_ids:
            await self.notif_service.notify_many_users(
                user_ids=volunteer_ids,
                notif_type=NotificationTypeEnum.event_status,
                title="Event status change",
                message=f"The organizer has changed the status of the event «{event['title']}» to «{new_status}».",
                related_entity_id=event_id
            )

        return await self._format_event_detail(updated)

    async def upload_event_photos(
        self, event_id: str, files: List[UploadFile], current_user: dict
    ) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["organizer_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the organizer of this event")

        allowed_types = ["image/jpeg", "image/png"]
        saved_urls = []

        for file in files:
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} has an invalid format. Only JPG and PNG are allowed"
                )

            ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
            unique_name = f"{event_id}_{uuid.uuid4().hex}.{ext}"
            file_path = os.path.join(EVENT_PHOTOS_DIR, unique_name)

            async with aiofiles.open(file_path, "wb") as out_file:
                content = await file.read()
                await out_file.write(content)

            saved_urls.append(f"/static/events/{unique_name}")

        updated = await self.event_repository.add_event_photos(event_id, saved_urls)
        return await self._format_event_detail(updated)

    async def delete_event(self, event_id: str, current_user: dict) -> None:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        is_owner = event["organizer_id"] == str(current_user["_id"])
        is_admin = current_user.get("role") == RoleEnum.admin.value

        if not (is_owner or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to delete the event")

        for photo_url in event.get("photos", []):
            filename = photo_url.split("/")[-1]
            file_path = os.path.join(EVENT_PHOTOS_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        await self.event_repository.cancel_active_applications_for_event(event_id)
        await self.event_repository.delete_event(event_id)

    async def get_pending_events_for_admin(self, current_user: dict) -> List[dict]:
        if current_user.get("role") != RoleEnum.admin.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Available only to Administrator")

        events = await self.event_repository.get_pending_moderation_events()
        result = []
        for e in events:
            result.append(await self._format_event_detail(e))
        return result

    async def moderate_event(
        self, event_id: str, mod_in: EventModerationRequest, current_user: dict
    ) -> dict:
        if current_user.get("role") != RoleEnum.admin.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Available to Administrator only")

        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        organizer = await self.user_repository.get_user_by_id(event["organizer_id"])
        organizer_email = organizer["email"] if organizer else None

        if mod_in.action == ModerationStatusEnum.approved:
            update_data = {
                "moderation_status": ModerationStatusEnum.approved.value,
                "status": EventLifecycleStatusEnum.open.value,
                "rejection_reason": None
            }
            notif_title = "Your event has been published!"
            notif_msg = (
                f"The administrator has approved your initiative «{event['title']}». "
                f"It now has the status «Open» and is displayed on the interactive map."
            )
        else:
            update_data = {
                "moderation_status": ModerationStatusEnum.rejected.value,
                "status": EventLifecycleStatusEnum.cancelled.value,
                "rejection_reason": mod_in.rejection_reason
            }
            notif_title = "Your event has been rejected by the moderator"
            notif_msg = (
                f"The initiative «{event['title']}» was rejected during moderation.\n"
                f"Reason: {mod_in.rejection_reason}"
            )

        updated = await self.event_repository.update_event(event_id, update_data)

        await self.notif_service.notify_user(
            user_id=event["organizer_id"],
            notif_type=NotificationTypeEnum.event_moderation,
            title=notif_title,
            message=notif_msg,
            related_entity_id=event_id,
            email_to=organizer_email
        )

        return await self._format_event_detail(updated)
