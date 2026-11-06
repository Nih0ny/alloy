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
from alloy.services.auth_service import AuthService
from alloy.services.profile_service import ProfileService
from alloy.services.event_service import EventService
from alloy.services.application_service import ApplicationService
from alloy.services.review_service import ReviewService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_database(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.mongo_client[settings.DATABASE_NAME]

def get_user_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> UserRepository:
    return UserRepository(db)

def get_event_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> EventRepository:
    return EventRepository(db)

def get_auth_service(user_repo: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repo)

def get_profile_service(user_repo: UserRepository = Depends(get_user_repository)) -> ProfileService:
    return ProfileService(user_repo)

def get_event_service(
    event_repo: EventRepository = Depends(get_event_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> EventService:
    return EventService(event_repo, user_repo)

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
    user_repo: UserRepository = Depends(get_user_repository)
) -> ApplicationService:
    return ApplicationService(app_repo, event_repo, user_repo)

def get_review_repository(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> ReviewRepository:
    return ReviewRepository(db)

def get_review_service(
    review_repo: ReviewRepository = Depends(get_review_repository),
    event_repo: EventRepository = Depends(get_event_repository),
    app_repo: ApplicationRepository = Depends(get_application_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> ReviewService:
    return ReviewService(review_repo, event_repo, app_repo, user_repo)

