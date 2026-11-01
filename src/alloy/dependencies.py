from typing import Optional
from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from alloy.core.config import settings
from alloy.repositories.user_repository import UserRepository
from alloy.services.auth_service import AuthService


def get_database(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.mongo_client[settings.DATABASE_NAME]

def get_user_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> UserRepository:
    return UserRepository(db)

def get_auth_service(user_repo: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repo)

