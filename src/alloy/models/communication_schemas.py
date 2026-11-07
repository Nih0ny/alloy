from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class CommentCreate(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Comment text (question to the organizer or clarification of details)"
    )
    reply_to_comment_id: Optional[str] = Field(
        None,
        description="Optional ID of the comment being replied to"
    )

    @field_validator("text")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Comment text cannot be empty")
        return cleaned


class CommentResponse(BaseModel):
    id: str
    event_id: str
    author_id: str
    author_name: str
    author_role: str
    author_avatar_url: Optional[str] = None
    text: str
    reply_to_comment_id: Optional[str] = None
    created_at: datetime


class DirectMessageCreate(BaseModel):
    recipient_id: str = Field(..., description="Message recipient ID")
    event_id: Optional[str] = Field(None, description="Optional link to a specific event")
    text: str = Field(..., min_length=1, max_length=2000, description="Message text")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty")
        return cleaned


class DirectMessageResponse(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    sender_avatar_url: Optional[str] = None
    recipient_id: str
    recipient_name: str
    recipient_avatar_url: Optional[str] = None
    event_id: Optional[str] = None
    text: str
    is_read: bool = False
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    interlocutor_id: str
    interlocutor_name: str
    interlocutor_role: str
    interlocutor_avatar_url: Optional[str] = None
    last_message_text: str
    last_message_at: datetime
    unread_count: int = 0


class SupportTicketStatusEnum(str, Enum):
    open = "New"
    in_progress = "In Progress"
    resolved = "Resolved"


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=3, max_length=150, description="Subject of the request")
    message: str = Field(..., min_length=10, max_length=3000, description="Detailed description of the issue or question")
    contact_email: Optional[EmailStr] = Field(
        None,
        description="Contact email for feedback (mandatory if requested by a Guest)"
    )


class SupportTicketUpdateStatus(BaseModel):
    status: SupportTicketStatusEnum
    admin_reply: Optional[str] = Field(None, max_length=2000, description="Support team comment or reply")


class SupportTicketResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    contact_email: EmailStr
    subject: str
    message: str
    status: SupportTicketStatusEnum
    admin_reply: Optional[str] = None
    created_at: datetime
    updated_at: datetime
