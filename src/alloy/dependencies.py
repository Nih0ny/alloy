from typing import Optional
from fastapi import Depends, Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from alloy.core.config import settings
from alloy.core import security
from alloy.repositories.user_repository import UserRepository
from alloy.repositories.event_repository import EventRepository
from alloy.repositories.application_repository import ApplicationRepository
from alloy.repositories.review_repository import ReviewRepository
from alloy.repositories.complaint_repository import ComplaintRepository
from alloy.services.auth_service import AuthService
from alloy.services.profile_service import ProfileService
from alloy.services.event_service import EventService
from alloy.services.application_service import ApplicationService
from alloy.services.review_service import ReviewService
from alloy.repositories.category_repository import CategoryRepository
from alloy.services.category_service import CategoryService
from alloy.repositories.communication_repository import (
    CommentRepository,
    MessageRepository,
    SupportRepository,
)
from alloy.services.communication_service import (
    CommentService,
    MessageService,
    SupportService,
)
from alloy.services.complaint_service import ComplaintService
from alloy.repositories.notification_repository import NotificationRepository
from alloy.services.notification_service import NotificationService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_database(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.mongo_client[settings.DATABASE_NAME]

def get_notification_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> NotificationRepository:
    return NotificationRepository(db)

def get_user_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> UserRepository:
    return UserRepository(db)

def get_notification_service(
    notif_repo: NotificationRepository = Depends(get_notification_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> NotificationService:
    return NotificationService(notif_repo, user_repo)

def get_event_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> EventRepository:
    return EventRepository(db)

def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    notif_service: NotificationService = Depends(get_notification_service)
) -> AuthService:
    return AuthService(user_repo, notif_service)

def get_profile_service(user_repo: UserRepository = Depends(get_user_repository)) -> ProfileService:
    return ProfileService(user_repo)

def get_event_service(
    event_repo: EventRepository = Depends(get_event_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    notif_service: NotificationService = Depends(get_notification_service)
) -> EventService:
    return EventService(event_repo, user_repo, notif_service)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepository = Depends(get_user_repository)
) -> dict:
    payload = security.decode_token(token)
    if not payload or payload.get("type") == "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    email = payload.get("sub")
    user = await user_repo.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.get("status") == "Blocked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")

    return user

async def get_verified_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if not current_user.get("is_email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must verify your email address to perform this action"
        )
    return current_user

async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Optional[dict]:
    if not token:
        return None
    try:
        return await get_current_user(token=token, user_repo=user_repo)
    except HTTPException:
        return None

def get_application_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> ApplicationRepository:
    return ApplicationRepository(db)

def get_application_service(
    app_repo: ApplicationRepository = Depends(get_application_repository),
    event_repo: EventRepository = Depends(get_event_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    notif_service: NotificationService = Depends(get_notification_service)
) -> ApplicationService:
    return ApplicationService(app_repo, event_repo, user_repo, notif_service)

def get_review_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> ReviewRepository:
    return ReviewRepository(db)

def get_review_service(
    review_repo: ReviewRepository = Depends(get_review_repository),
    event_repo: EventRepository = Depends(get_event_repository),
    app_repo: ApplicationRepository = Depends(get_application_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    notif_service: NotificationService = Depends(get_notification_service)
) -> ReviewService:
    return ReviewService(review_repo, event_repo, app_repo, user_repo, notif_service)

def get_category_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> CategoryRepository:
    return CategoryRepository(db)

def get_category_service(
    category_repo: CategoryRepository = Depends(get_category_repository)
) -> CategoryService:
    return CategoryService(category_repo)

def get_comment_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> CommentRepository:
    return CommentRepository(db)


def get_message_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> MessageRepository:
    return MessageRepository(db)


def get_support_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> SupportRepository:
    return SupportRepository(db)


def get_comment_service(
    comment_repo: CommentRepository = Depends(get_comment_repository),
    event_repo: EventRepository = Depends(get_event_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    notif_service: NotificationService = Depends(get_notification_service)
) -> CommentService:
    return CommentService(comment_repo, event_repo, user_repo, notif_service)

def get_message_service(
    message_repo: MessageRepository = Depends(get_message_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    event_repo: EventRepository = Depends(get_event_repository)
) -> MessageService:
    return MessageService(message_repo, user_repo, event_repo)


def get_support_service(
    support_repo: SupportRepository = Depends(get_support_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> SupportService:
    return SupportService(support_repo, user_repo)


def get_complaint_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> ComplaintRepository:
    return ComplaintRepository(db)

def get_complaint_service(
    complaint_repo: ComplaintRepository = Depends(get_complaint_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    event_repo: EventRepository = Depends(get_event_repository),
    comment_repo: CommentRepository = Depends(get_comment_repository),
    notif_service: NotificationService = Depends(get_notification_service)
) -> ComplaintService:
    return ComplaintService(complaint_repo, user_repo, event_repo, comment_repo, notif_service)

