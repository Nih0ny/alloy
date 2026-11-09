from datetime import datetime, UTC
from typing import List
from fastapi import HTTPException, status

from alloy.repositories.application_repository import ApplicationRepository
from alloy.repositories.event_repository import EventRepository
from alloy.repositories.user_repository import UserRepository
from alloy.models.application_schemas import (
    ApplicationCreate,
    ApplicationReviewRequest,
    ApplicationStatusEnum,
    OrganizerDecisionEnum,
)
from alloy.models.event_schemas import EventLifecycleStatusEnum
from alloy.models.auth_schemas import RoleEnum
from alloy.services.notification_service import NotificationService
from alloy.models.notification_schemas import NotificationTypeEnum

class ApplicationService:
    def __init__(
        self,
        app_repository: ApplicationRepository,
        event_repository: EventRepository,
        user_repository: UserRepository,
        notif_service: NotificationService
    ):
        self.app_repository = app_repository
        self.event_repository = event_repository
        self.user_repository = user_repository
        self.notif_service = notif_service

    async def _format_volunteer_application(self, app: dict) -> dict:
        event = await self.event_repository.get_event_by_id(app["event_id"])
        event_title = event["title"] if event else "Deleted Event"
        event_date = event.get("event_date") if event else None
        event_status = event["status"] if event else EventLifecycleStatusEnum.cancelled.value

        can_withdraw = (
            event_status not in [
                EventLifecycleStatusEnum.completed.value,
                EventLifecycleStatusEnum.cancelled.value
            ]
            and app["status"] in [
                ApplicationStatusEnum.pending.value,
                ApplicationStatusEnum.approved.value
            ]
        )

        organizer_contacts = None
        if app["status"] == ApplicationStatusEnum.approved.value and event:
            organizer = await self.user_repository.get_user_by_id(event["organizer_id"])
            if organizer:
                org_profile = organizer.get("profile", {})
                organizer_contacts = {
                    "full_name": org_profile.get("full_name"),
                    "email": organizer["email"],
                    "phone": org_profile.get("phone")
                }

        return {
            "id": str(app["_id"]),
            "event_id": app["event_id"],
            "event_title": event_title,
            "event_date": event_date,
            "event_status": event_status,
            "volunteer_id": app["volunteer_id"],
            "motivation_letter": app.get("motivation_letter"),
            "status": app["status"],
            "rejection_reason": app.get("rejection_reason"),
            "can_withdraw": can_withdraw,
            "organizer_contacts": organizer_contacts,
            "created_at": app["created_at"],
            "updated_at": app["updated_at"]
        }

    async def submit_application(
        self, event_id: str, app_in: ApplicationCreate, current_user: dict
    ) -> dict:
        if current_user.get("role") != RoleEnum.volunteer.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only users with the 'Volunteer' role can apply for participation"
            )

        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event.get("status") != EventLifecycleStatusEnum.open.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application acceptance is closed or the event is not yet open for participation"
            )

        volunteer_id = str(current_user["_id"])
        volunteer_name = current_user.get("profile", {}).get("full_name") or current_user["email"]
        existing_app = await self.app_repository.get_by_event_and_volunteer(event_id, volunteer_id)

        if existing_app:
            if existing_app["status"] != ApplicationStatusEnum.withdrawn.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You have already applied for this event"
                )
            saved_app = await self.app_repository.update_application(
                str(existing_app["_id"]),
                {
                    "motivation_letter": app_in.motivation_letter,
                    "agreed_to_share_contacts": app_in.agreed_to_share_contacts,
                    "status": ApplicationStatusEnum.pending.value,
                    "rejection_reason": None
                }
            )
        else:
            now = datetime.utcnow()
            app_dict = {
                "event_id": event_id,
                "volunteer_id": volunteer_id,
                "motivation_letter": app_in.motivation_letter,
                "agreed_to_share_contacts": app_in.agreed_to_share_contacts,
                "status": ApplicationStatusEnum.pending.value,
                "rejection_reason": None,
                "created_at": now,
                "updated_at": now
            }
            saved_app = await self.app_repository.create_application(app_dict)

        await self.notif_service.notify_user(
            user_id=event["organizer_id"],
            notif_type=NotificationTypeEnum.new_application,
            title="New application from a volunteer",
            message=f"Volunteer {volunteer_name} has applied to participate in your event «{event['title']}».",
            related_entity_id=event_id
        )

        return await self._format_volunteer_application(saved_app)

    async def get_my_applications(self, current_user: dict) -> List[dict]:
        if current_user.get("role") != RoleEnum.volunteer.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Available only for Volunteers"
            )
        apps = await self.app_repository.get_by_volunteer(str(current_user["_id"]))
        return [await self._format_volunteer_application(a) for a in apps]

    async def get_application_details(self, application_id: str, current_user: dict) -> dict:
        app = await self.app_repository.get_by_id(application_id)
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        event = await self.event_repository.get_event_by_id(app["event_id"])
        user_id = str(current_user["_id"])
        is_volunteer_owner = app["volunteer_id"] == user_id
        is_event_organizer = event and event["organizer_id"] == user_id
        is_admin = current_user.get("role") == RoleEnum.admin.value

        if not (is_volunteer_owner or is_event_organizer or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this application")

        return await self._format_volunteer_application(app)

    async def withdraw_application(self, application_id: str, current_user: dict) -> dict:
        app = await self.app_repository.get_by_id(application_id)
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        if app["volunteer_id"] != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only withdraw your own application"
            )

        if app["status"] == ApplicationStatusEnum.withdrawn.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Application is already withdrawn")

        if app["status"] == ApplicationStatusEnum.rejected.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot withdraw an application that has already been rejected by the organizer"
            )

        event = await self.event_repository.get_event_by_id(app["event_id"])
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["status"] in [
            EventLifecycleStatusEnum.completed.value,
            EventLifecycleStatusEnum.cancelled.value
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot withdraw application as the event has already been completed or cancelled"
            )

        was_approved = app["status"] == ApplicationStatusEnum.approved.value
        updated_app = await self.app_repository.update_application(
            application_id,
            {"status": ApplicationStatusEnum.withdrawn.value}
        )

        if was_approved:
            current_approved = max(0, event.get("approved_volunteers_count", 1) - 1)
            quota = event.get("volunteer_quota", 1)
            new_event_status = None

            if (
                event["status"] == EventLifecycleStatusEnum.in_process.value
                and current_approved < quota
            ):
                new_event_status = EventLifecycleStatusEnum.open.value

            await self.event_repository.increment_approved_volunteers(
                app["event_id"], delta=-1, new_status=new_event_status
            )

        volunteer_name = current_user.get("profile", {}).get("full_name") or current_user["email"]
        await self.notif_service.notify_user(
            user_id=event["organizer_id"],
            notif_type=NotificationTypeEnum.application_withdrawn,
            title="Volunteer withdrew application",
            message=f"Volunteer {volunteer_name} has cancelled their participation in the event «{event['title']}».",
            related_entity_id=app["event_id"]
        )

        return await self._format_volunteer_application(updated_app)

    async def get_event_applications_for_organizer(
        self, event_id: str, current_user: dict
    ) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        is_owner = event["organizer_id"] == str(current_user["_id"])
        is_admin = current_user.get("role") == RoleEnum.admin.value
        if not (is_owner or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the Organizer of this event can view submitted applications"
            )

        raw_apps = await self.app_repository.get_by_event(event_id)
        applicant_items = []

        for app in raw_apps:
            volunteer = await self.user_repository.get_user_by_id(app["volunteer_id"])
            vol_profile = volunteer.get("profile", {}) if volunteer else {}
            vol_name = (
                vol_profile.get("full_name")
                or (volunteer["email"] if volunteer else "Unknown Volunteer")
            )

            vol_phone = (
                vol_profile.get("phone")
                if app["status"] == ApplicationStatusEnum.approved.value
                else None
            )

            applicant_items.append({
                "application_id": str(app["_id"]),
                "volunteer_id": app["volunteer_id"],
                "volunteer_name": vol_name,
                "volunteer_avatar_url": vol_profile.get("avatar_url"),
                "volunteer_rating": vol_profile.get("rating", 0.0),
                "volunteer_phone": vol_phone,
                "motivation_letter": app.get("motivation_letter"),
                "status": app["status"],
                "rejection_reason": app.get("rejection_reason"),
                "created_at": app["created_at"]
            })

        approved = event.get("approved_volunteers_count", 0)
        quota = event.get("volunteer_quota", 1)

        return {
            "event_id": str(event["_id"]),
            "event_title": event["title"],
            "event_status": event["status"],
            "progress_text": f"Confirmed: {approved} of {quota}",
            "volunteer_quota": quota,
            "approved_volunteers_count": approved,
            "applications": applicant_items
        }

    async def review_application(
        self, application_id: str, review_in: ApplicationReviewRequest, current_user: dict
    ) -> dict:
        app = await self.app_repository.get_by_id(application_id)
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        event = await self.event_repository.get_event_by_id(app["event_id"])
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event["organizer_id"] != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not the organizer of this event"
            )

        if event["status"] in [
            EventLifecycleStatusEnum.completed.value,
            EventLifecycleStatusEnum.cancelled.value
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot review applications for a completed or cancelled event"
            )

        if app["status"] == ApplicationStatusEnum.withdrawn.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The volunteer has already withdrawn this application"
            )

        if app["status"] == review_in.status.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The application already has the status '{review_in.status.value}'"
            )

        approved_count = event.get("approved_volunteers_count", 0)
        quota = event.get("volunteer_quota", 1)

        if review_in.status == OrganizerDecisionEnum.approved:
            if approved_count >= quota:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The required volunteer quota for this event has already been fully reached"
                )

            updated_app = await self.app_repository.update_application(
                application_id,
                {
                    "status": ApplicationStatusEnum.approved.value,
                    "rejection_reason": None
                }
            )

            new_approved_count = approved_count + 1
            new_event_status = None
            if new_approved_count >= quota and event["status"] == EventLifecycleStatusEnum.open.value:
                new_event_status = EventLifecycleStatusEnum.in_process.value

            await self.event_repository.increment_approved_volunteers(
                app["event_id"], delta=1, new_status=new_event_status
            )

            await self.notif_service.notify_user(
                user_id=app["volunteer_id"],
                notif_type=NotificationTypeEnum.application_status,
                title="Your application has been approved!",
                message=(
                    f"The organizer has approved your application to participate in the event «{event['title']}». "
                    f"The organizer's contact details are now available in your application details."
                ),
                related_entity_id=str(updated_app["_id"])
            )
            return await self._format_volunteer_application(updated_app)

        was_approved = app["status"] == ApplicationStatusEnum.approved.value
        updated_app = await self.app_repository.update_application(
            application_id,
            {
                "status": ApplicationStatusEnum.rejected.value,
                "rejection_reason": review_in.rejection_reason
            }
        )

        if was_approved:
            new_approved_count = max(0, approved_count - 1)
            new_event_status = None
            if (
                event["status"] == EventLifecycleStatusEnum.in_process.value
                and new_approved_count < quota
            ):
                new_event_status = EventLifecycleStatusEnum.open.value

            await self.event_repository.increment_approved_volunteers(
                app["event_id"], delta=-1, new_status=new_event_status
            )

        reason_suffix = f" Reason: {review_in.rejection_reason}" if review_in.rejection_reason else ""
        await self.notif_service.notify_user(
            user_id=app["volunteer_id"],
            notif_type=NotificationTypeEnum.application_status,
            title="Your application has been rejected",
            message=f"Unfortunately, the organizer has rejected your application for the event «{event['title']}».{reason_suffix}",
            related_entity_id=str(updated_app["_id"])
        )

        return await self._format_volunteer_application(updated_app)

