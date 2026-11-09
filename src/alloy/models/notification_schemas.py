from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class NotificationTypeEnum(str, Enum):
    event_moderation = "Event moderation"
    new_application = "New application"
    application_status = "Application status"
    application_withdrawn = "Application withdrawal"
    event_status = "Event status change"
    new_review = "New review"
    new_comment = "New comment"
    account_security = "Account security"

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: NotificationTypeEnum
    title: str
    message: str
    related_entity_id: Optional[str] = Field(None, description="ID of the related event or application for in-app navigation")
    is_read: bool = False
    created_at: datetime

class NotificationListResponse(BaseModel):
    unread_count: int
    items: List[NotificationResponse]
