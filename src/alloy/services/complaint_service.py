import logging
from datetime import datetime, UTC
from typing import List, Optional
from fastapi import HTTPException, status

from alloy.repositories.complaint_repository import ComplaintRepository
from alloy.repositories.user_repository import UserRepository
from alloy.repositories.event_repository import EventRepository
from alloy.repositories.communication_repository import CommentRepository
from alloy.models.complaint_schemas import (
    ComplaintCreate,
    ComplaintRejectRequest,
    UserBlockRequest,
    ComplaintTargetTypeEnum,
    ComplaintStatusEnum,
)
from alloy.models.auth_schemas import RoleEnum, StatusEnum
from alloy.services.notification_service import NotificationService
from alloy.models.notification_schemas import NotificationTypeEnum

logger = logging.getLogger("alloy.security")

class ComplaintService:
    def __init__(
        self,
        complaint_repository: ComplaintRepository,
        user_repository: UserRepository,
        event_repository: EventRepository,
        comment_repository: CommentRepository,
        notif_service: NotificationService
    ):
        self.complaint_repository = complaint_repository
        self.user_repository = user_repository
        self.event_repository = event_repository
        self.comment_repository = comment_repository
        self.notif_service = notif_service

    def _ensure_admin(self, current_user: dict) -> None:
        if current_user.get("role") != RoleEnum.admin.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access allowed only for Administrator"
            )

    def _user_display_name(self, user: Optional[dict]) -> str:
        if not user:
            return "Unknown user"
        return user.get("profile", {}).get("full_name") or user["email"]

    async def _resolve_target_details(
        self, target_type: str, target_id: str
    ) -> tuple[str, Optional[str], Optional[str]]:
        if target_type == ComplaintTargetTypeEnum.user.value:
            target_user = await self.user_repository.get_user_by_id(target_id)
            if not target_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            name = self._user_display_name(target_user)
            return f"User profile: {name}", str(target_user["_id"]), name

        if target_type == ComplaintTargetTypeEnum.event.value:
            event = await self.event_repository.get_event_by_id(target_id)
            if not event:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            org = await self.user_repository.get_user_by_id(event["organizer_id"])
            org_name = self._user_display_name(org)
            return f"Event: «{event['title']}»", event["organizer_id"], org_name

        if target_type == ComplaintTargetTypeEnum.comment.value:
            comment = await self.comment_repository.get_by_id(target_id)
            if not comment:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
            author = await self.user_repository.get_user_by_id(comment["author_id"])
            author_name = self._user_display_name(author)
            snippet = comment["text"][:60] + ("..." if len(comment["text"]) > 60 else "")
            return f"Comment: «{snippet}»", comment["author_id"], author_name

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown complaint target type")

    async def _format_complaint(self, doc: dict) -> dict:
        reporter = await self.user_repository.get_user_by_id(doc["reporter_id"])
        accused = (
            await self.user_repository.get_user_by_id(doc["accused_user_id"])
            if doc.get("accused_user_id") else None
        )
        return {
            "id": str(doc["_id"]),
            "reporter_id": doc["reporter_id"],
            "reporter_name": self._user_display_name(reporter),
            "target_type": doc["target_type"],
            "target_id": doc["target_id"],
            "target_summary": doc.get("target_summary", ""),
            "accused_user_id": doc.get("accused_user_id"),
            "accused_user_name": self._user_display_name(accused) if accused else doc.get("accused_user_name"),
            "violation_category": doc["violation_category"],
            "description": doc["description"],
            "status": doc["status"],
            "admin_note": doc.get("admin_note"),
            "created_at": doc["created_at"],
            "resolved_at": doc.get("resolved_at")
        }

    async def submit_complaint(
        self, complaint_in: ComplaintCreate, current_user: dict
    ) -> dict:
        target_summary, accused_user_id, accused_user_name = await self._resolve_target_details(
            complaint_in.target_type.value, complaint_in.target_id
        )

        reporter_id = str(current_user["_id"])
        if accused_user_id == reporter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot file a complaint against your own profile or content"
            )

        now = datetime.now(UTC)
        complaint_doc = {
            "reporter_id": reporter_id,
            "target_type": complaint_in.target_type.value,
            "target_id": complaint_in.target_id,
            "target_summary": target_summary,
            "accused_user_id": accused_user_id,
            "accused_user_name": accused_user_name,
            "violation_category": complaint_in.violation_category,
            "description": complaint_in.description,
            "status": ComplaintStatusEnum.pending.value,
            "admin_note": None,
            "created_at": now,
            "resolved_at": None
        }
        created = await self.complaint_repository.create_complaint(complaint_doc)
        return await self._format_complaint(created)

    async def get_complaints_for_admin(
        self, current_user: dict, status_filter: Optional[str] = None
    ) -> List[dict]:
        self._ensure_admin(current_user)
        complaints = await self.complaint_repository.get_all_complaints(status_filter)
        return [await self._format_complaint(c) for c in complaints]

    async def get_complaint_details_for_admin(
        self, complaint_id: str, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)
        complaint = await self.complaint_repository.get_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        return await self._format_complaint(complaint)

    async def reject_complaint(
        self, complaint_id: str, reject_in: ComplaintRejectRequest, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)
        complaint = await self.complaint_repository.get_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

        updated = await self.complaint_repository.update_complaint(
            complaint_id,
            {
                "status": ComplaintStatusEnum.rejected.value,
                "admin_note": reject_in.admin_note,
                "resolved_at": datetime.now(UTC)
            }
        )
        return await self._format_complaint(updated)

    async def delete_reported_content_and_resolve(
        self, complaint_id: str, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)
        complaint = await self.complaint_repository.get_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

        target_type = complaint["target_type"]
        target_id = complaint["target_id"]

        if target_type == ComplaintTargetTypeEnum.comment.value:
            await self.comment_repository.delete_comment(target_id)
        elif target_type == ComplaintTargetTypeEnum.event.value:
            await self.event_repository.cancel_active_applications_for_event(target_id)
            await self.event_repository.delete_event(target_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For user complaints, please use the account blocking endpoint"
            )

        updated = await self.complaint_repository.update_complaint(
            complaint_id,
            {
                "status": ComplaintStatusEnum.resolved.value,
                "admin_note": f"Content ({target_type}) deleted by Administrator",
                "resolved_at": datetime.now(UTC)
            }
        )
        return await self._format_complaint(updated)

    def _format_registry_user(self, user: dict) -> dict:
        profile = user.get("profile", {})
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "full_name": profile.get("full_name") or user["email"],
            "role": user["role"],
            "status": user.get("status", StatusEnum.active.value),
            "rating": profile.get("rating", 0.0),
            "block_reason": user.get("block_reason"),
            "blocked_at": user.get("blocked_at")
        }

    async def get_users_registry(
        self,
        current_user: dict,
        role_filter: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[dict]:
        self._ensure_admin(current_user)
        users = await self.complaint_repository.get_all_users_registry(role_filter, status_filter)
        return [self._format_registry_user(u) for u in users]

    async def block_user(
        self, target_user_id: str, block_in: UserBlockRequest, current_user: dict
    ) -> dict:
        self._ensure_admin(current_user)

        target_user = await self.user_repository.get_user_by_id(target_user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if target_user.get("role") == RoleEnum.admin.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot block another administrator"
            )

        if target_user.get("status") == StatusEnum.blocked.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account is already blocked"
            )

        await self.complaint_repository.apply_user_block_cascade(
            user_id=target_user_id,
            reason=block_in.reason,
            complaint_id=block_in.complaint_id
        )

        await self.notif_service.notify_user(
            user_id=target_user_id,
            notif_type=NotificationTypeEnum.account_security,
            title="Your account on the Xelp platform has been blocked",
            message=(
                f"Your account has been blocked by the administrator due to a violation of community guidelines.\n"
                f"Reason for blocking: {block_in.reason}"
            ),
            email_to=target_user["email"]
        )

        logger.info(
            "SECURITY_EVENT: user_blocked",
            extra={
                "event_type": "security_audit",
                "user_id": target_user_id,
                "recipient": target_user["email"]
            }
        )

        updated_user = await self.user_repository.get_user_by_id(target_user_id)
        return self._format_registry_user(updated_user)

    async def unblock_user(self, target_user_id: str, current_user: dict) -> dict:
        self._ensure_admin(current_user)

        target_user = await self.user_repository.get_user_by_id(target_user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        await self.complaint_repository.users_collection.update_one(
            {"_id": target_user["_id"]},
            {
                "$set": {
                    "status": StatusEnum.active.value,
                    "block_reason": None,
                    "blocked_at": None
                }
            }
        )
        updated_user = await self.user_repository.get_user_by_id(target_user_id)
        return self._format_registry_user(updated_user)
