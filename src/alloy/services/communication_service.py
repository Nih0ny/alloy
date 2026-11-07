from datetime import datetime, UTC
from typing import List, Optional
from fastapi import HTTPException, status

from alloy.repositories.communication_repository import (
    CommentRepository,
    MessageRepository,
    SupportRepository,
)
from alloy.repositories.event_repository import EventRepository
from alloy.repositories.user_repository import UserRepository
from alloy.models.communication_schemas import (
    CommentCreate,
    DirectMessageCreate,
    SupportTicketCreate,
    SupportTicketUpdateStatus,
    SupportTicketStatusEnum,
)
from alloy.models.event_schemas import EventLifecycleStatusEnum
from alloy.models.auth_schemas import RoleEnum


class CommentService:
    def __init__(
        self,
        comment_repository: CommentRepository,
        event_repository: EventRepository,
        user_repository: UserRepository
    ):
        self.comment_repository = comment_repository
        self.event_repository = event_repository
        self.user_repository = user_repository

    async def _format_comment(self, comment: dict) -> dict:
        author = await self.user_repository.get_user_by_id(comment["author_id"])
        profile = author.get("profile", {}) if author else {}
        author_name = profile.get("full_name") or (author["email"] if author else "Unknown user")
        author_role = author.get("role", "Volunteer") if author else "Volunteer"

        return {
            "id": str(comment["_id"]),
            "event_id": comment["event_id"],
            "author_id": comment["author_id"],
            "author_name": author_name,
            "author_role": author_role,
            "author_avatar_url": profile.get("avatar_url"),
            "text": comment["text"],
            "reply_to_comment_id": comment.get("reply_to_comment_id"),
            "created_at": comment["created_at"]
        }

    async def get_event_comments(self, event_id: str, skip: int = 0, limit: int = 100) -> List[dict]:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        comments = await self.comment_repository.get_by_event(event_id, skip, limit)
        return [await self._format_comment(c) for c in comments]

    async def add_comment(
        self, event_id: str, comment_in: CommentCreate, current_user: dict
    ) -> dict:
        event = await self.event_repository.get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event.get("status") != EventLifecycleStatusEnum.open.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Commenting is available only for events in 'Open' status"
            )

        if comment_in.reply_to_comment_id:
            parent_comment = await self.comment_repository.get_by_id(comment_in.reply_to_comment_id)
            if not parent_comment or parent_comment["event_id"] != event_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The comment you are replying to was not found within this event"
                )

        comment_doc = {
            "event_id": event_id,
            "author_id": str(current_user["_id"]),
            "text": comment_in.text,
            "reply_to_comment_id": comment_in.reply_to_comment_id,
            "created_at": datetime.now(UTC)
        }
        created = await self.comment_repository.create_comment(comment_doc)
        return await self._format_comment(created)

    async def delete_comment(self, comment_id: str, current_user: dict) -> None:
        comment = await self.comment_repository.get_by_id(comment_id)
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

        user_id = str(current_user["_id"])
        is_author = comment["author_id"] == user_id
        is_admin = current_user.get("role") == RoleEnum.admin.value

        event = await self.event_repository.get_event_by_id(comment["event_id"])
        is_event_organizer = event is not None and event["organizer_id"] == user_id

        if not (is_author or is_event_organizer or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete this comment"
            )

        await self.comment_repository.delete_comment(comment_id)


class MessageService:
    def __init__(
        self,
        message_repository: MessageRepository,
        user_repository: UserRepository,
        event_repository: EventRepository
    ):
        self.message_repository = message_repository
        self.user_repository = user_repository
        self.event_repository = event_repository

    def _get_user_display(self, user: Optional[dict]) -> tuple[str, Optional[str], str]:
        if not user:
            return "Unknown user", None, "Volunteer"
        profile = user.get("profile", {})
        name = profile.get("full_name") or user["email"]
        return name, profile.get("avatar_url"), user.get("role", "Volunteer")

    async def _format_message(self, msg: dict) -> dict:
        sender = await self.user_repository.get_user_by_id(msg["sender_id"])
        recipient = await self.user_repository.get_user_by_id(msg["recipient_id"])
        sender_name, sender_avatar, _ = self._get_user_display(sender)
        recipient_name, recipient_avatar, _ = self._get_user_display(recipient)

        return {
            "id": str(msg["_id"]),
            "sender_id": msg["sender_id"],
            "sender_name": sender_name,
            "sender_avatar_url": sender_avatar,
            "recipient_id": msg["recipient_id"],
            "recipient_name": recipient_name,
            "recipient_avatar_url": recipient_avatar,
            "event_id": msg.get("event_id"),
            "text": msg["text"],
            "is_read": msg.get("is_read", False),
            "created_at": msg["created_at"]
        }

    async def send_message(self, msg_in: DirectMessageCreate, current_user: dict) -> dict:
        sender_id = str(current_user["_id"])
        if msg_in.recipient_id == sender_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send a message to yourself"
            )

        recipient = await self.user_repository.get_user_by_id(msg_in.recipient_id)
        if not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

        if recipient.get("status") == "Blocked":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send a message to a blocked user"
            )

        if msg_in.event_id:
            event = await self.event_repository.get_event_by_id(msg_in.event_id)
            if not event:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked event not found")

        msg_doc = {
            "sender_id": sender_id,
            "recipient_id": msg_in.recipient_id,
            "event_id": msg_in.event_id,
            "text": msg_in.text,
            "is_read": False,
            "created_at": datetime.now(UTC)
        }
        created = await self.message_repository.create_message(msg_doc)
        return await self._format_message(created)

    async def get_conversation(
        self, interlocutor_id: str, current_user: dict, skip: int = 0, limit: int = 100
    ) -> List[dict]:
        current_user_id = str(current_user["_id"])
        interlocutor = await self.user_repository.get_user_by_id(interlocutor_id)
        if not interlocutor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interlocutor not found")

        await self.message_repository.mark_conversation_as_read(current_user_id, interlocutor_id)
        messages = await self.message_repository.get_conversation_messages(
            current_user_id, interlocutor_id, skip, limit
        )
        return [await self._format_message(m) for m in messages]

    async def get_my_conversations(self, current_user: dict) -> List[dict]:
        current_user_id = str(current_user["_id"])
        all_messages = await self.message_repository.get_user_messages_all(current_user_id)

        dialogs: dict[str, dict] = {}
        for msg in all_messages:
            other_id = msg["recipient_id"] if msg["sender_id"] == current_user_id else msg["sender_id"]
            if other_id not in dialogs:
                dialogs[other_id] = {
                    "last_message_text": msg["text"],
                    "last_message_at": msg["created_at"],
                    "unread_count": 0
                }
            if msg["recipient_id"] == current_user_id and not msg.get("is_read", False):
                dialogs[other_id]["unread_count"] += 1

        result = []
        for other_id, info in dialogs.items():
            other_user = await self.user_repository.get_user_by_id(other_id)
            name, avatar, role = self._get_user_display(other_user)
            result.append({
                "interlocutor_id": other_id,
                "interlocutor_name": name,
                "interlocutor_role": role,
                "interlocutor_avatar_url": avatar,
                "last_message_text": info["last_message_text"],
                "last_message_at": info["last_message_at"],
                "unread_count": info["unread_count"]
            })
        return result


class SupportService:
    def __init__(self, support_repository: SupportRepository, user_repository: UserRepository):
        self.support_repository = support_repository
        self.user_repository = user_repository

    def _format_ticket(self, ticket: dict) -> dict:
        return {
            "id": str(ticket["_id"]),
            "user_id": ticket.get("user_id"),
            "user_name": ticket.get("user_name"),
            "contact_email": ticket["contact_email"],
            "subject": ticket["subject"],
            "message": ticket["message"],
            "status": ticket["status"],
            "admin_reply": ticket.get("admin_reply"),
            "created_at": ticket["created_at"],
            "updated_at": ticket["updated_at"]
        }

    async def create_support_ticket(
        self, ticket_in: SupportTicketCreate, current_user: Optional[dict] = None
    ) -> dict:
        contact_email = ticket_in.contact_email or (current_user["email"] if current_user else None)
        if not contact_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="contact_email is required for unauthorized users"
            )

        user_id = str(current_user["_id"]) if current_user else None
        user_name = (
            current_user.get("profile", {}).get("full_name") or current_user["email"]
            if current_user else "Guest"
        )

        now = datetime.now(UTC)
        ticket_doc = {
            "user_id": user_id,
            "user_name": user_name,
            "contact_email": contact_email,
            "subject": ticket_in.subject.strip(),
            "message": ticket_in.message.strip(),
            "status": SupportTicketStatusEnum.open.value,
            "admin_reply": None,
            "created_at": now,
            "updated_at": now
        }
        created = await self.support_repository.create_ticket(ticket_doc)
        return self._format_ticket(created)

    async def get_my_tickets(self, current_user: dict) -> List[dict]:
        tickets = await self.support_repository.get_tickets_by_user(str(current_user["_id"]))
        return [self._format_ticket(t) for t in tickets]

    async def get_all_tickets_for_admin(
        self, current_user: dict, status_filter: Optional[str] = None
    ) -> List[dict]:
        if current_user.get("role") != RoleEnum.admin.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Available only to the Administrator")
        tickets = await self.support_repository.get_all_tickets(status_filter)
        return [self._format_ticket(t) for t in tickets]

    async def update_ticket_by_admin(
        self, ticket_id: str, update_in: SupportTicketUpdateStatus, current_user: dict
    ) -> dict:
        if current_user.get("role") != RoleEnum.admin.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Available only to the Administrator")

        ticket = await self.support_repository.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")

        updated = await self.support_repository.update_ticket(
            ticket_id,
            {
                "status": update_in.status.value,
                "admin_reply": update_in.admin_reply
            }
        )
        return self._format_ticket(updated)
