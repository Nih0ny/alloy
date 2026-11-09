import asyncio
import logging
import smtplib
import httpx2
import base64
from datetime import datetime, UTC
from email.message import EmailMessage
from typing import List, Optional
from fastapi import HTTPException, status

from alloy.core.config import settings
from alloy.repositories.notification_repository import NotificationRepository
from alloy.models.notification_schemas import NotificationTypeEnum

logger = logging.getLogger("alloy.notifications")

class NotificationService:
    def __init__(self, notif_repo: NotificationRepository):
        self.notif_repo = notif_repo

    def _format_notification(self, doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "user_id": doc["user_id"],
            "type": doc["type"],
            "title": doc["title"],
            "message": doc["message"],
            "related_entity_id": doc.get("related_entity_id"),
            "is_read": doc.get("is_read", False),
            "created_at": doc["created_at"]
        }

    async def notify_user(
        self,
        user_id: str,
        notif_type: NotificationTypeEnum,
        title: str,
        message: str,
        related_entity_id: Optional[str] = None,
        email_to: Optional[str] = None
    ) -> dict:
        doc = {
            "user_id": user_id,
            "type": notif_type.value,
            "title": title,
            "message": message,
            "related_entity_id": related_entity_id,
            "is_read": False,
            "created_at": datetime.now(UTC)
        }
        created = await self.notif_repo.create_notification(doc)

        if email_to:
            asyncio.create_task(self.send_email_async(email_to, title, message))

        return self._format_notification(created)

    async def notify_many_users(
        self,
        user_ids: List[str],
        notif_type: NotificationTypeEnum,
        title: str,
        message: str,
        related_entity_id: Optional[str] = None
    ) -> None:
        now = datetime.now(UTC)
        docs = [
            {
                "user_id": uid,
                "type": notif_type.value,
                "title": title,
                "message": message,
                "related_entity_id": related_entity_id,
                "is_read": False,
                "created_at": now
            }
            for uid in set(user_ids)
        ]
        await self.notif_repo.create_many_notifications(docs)

    def _send_smtp_sync(self, to_email: str, subject: str, body: str) -> None:
        def get_fresh_access_token():
            token_url = "https://oauth2.googleapis.com/token"
            payload = {
                "client_id": settings.SMTP_CLIENT_ID,
                "client_secret": settings.SMTP_CLIENT_SECRET,
                "refresh_token": settings.SMTP_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            }

            with httpx2.Client() as client:
                response = client.post(token_url, data=payload)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Failed to refresh SMTP token: {response.text}"
                    )
                return response.json()["access_token"]

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        msg.set_content(body)

        access_token = get_fresh_access_token()

        auth_string = f"user={settings.SMTP_USER}\x01auth=Bearer {access_token}\x01\x01"
        auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            code, response = server.docmd("AUTH", f"XOAUTH2 {auth_base64}")
            if code != 235:
                raise Exception(f"XOAUTH2 authorization failed: {code}, {response}")

            server.send_message(msg)

    async def send_email_async(self, to_email: str, subject: str, body: str) -> None:
        if not settings.SMTP_HOST:
            logger.info(
                "EMAIL_DISPATCH_SIMULATED",
                extra={"event_type": "email_simulated", "recipient": to_email, "subject": subject}
            )
            return

        try:
            await asyncio.to_thread(self._send_smtp_sync, to_email, subject, body)
            logger.info(
                "EMAIL_SENT_SUCCESSFULLY",
                extra={"event_type": "email_sent", "recipient": to_email, "subject": subject}
            )
        except Exception as exc:
            logger.error(
                f"EMAIL_SEND_FAILED: {exc}",
                extra={"event_type": "email_error", "recipient": to_email}
            )

    async def get_my_notifications(
        self, current_user: dict, unread_only: bool = False, skip: int = 0, limit: int = 50
    ) -> dict:
        user_id = str(current_user["_id"])
        items = await self.notif_repo.get_user_notifications(user_id, unread_only, skip, limit)
        unread_count = await self.notif_repo.count_unread(user_id)
        return {
            "unread_count": unread_count,
            "items": [self._format_notification(i) for i in items]
        }

    async def mark_notification_read(self, notification_id: str, current_user: dict) -> dict:
        updated = await self.notif_repo.mark_as_read(notification_id, str(current_user["_id"]))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        return self._format_notification(updated)

    async def mark_all_read(self, current_user: dict) -> dict:
        count = await self.notif_repo.mark_all_as_read(str(current_user["_id"]))
        return {"message": "All notifications marked as read", "updated_count": count}
