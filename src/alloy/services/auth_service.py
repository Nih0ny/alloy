from fastapi import HTTPException, status

from alloy.repositories.user_repository import UserRepository
from alloy.models.auth_schemas import UserCreate, StatusEnum
from alloy.core import security

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register_user(self, user_in: UserCreate) -> dict:
        existing_user = await self.user_repo.get_user_by_email(user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists"
            )

        hashed_password = security.get_password_hash(user_in.password)

        user_dict = {
            "email": user_in.email,
            "hashed_password": hashed_password,
            "role": user_in.role.value,
            "status": StatusEnum.active.value,
            "profile": {
                "full_name": None,      
                "phone": None,          
                "avatar_url": None,     
                "description": None,    
                "rating": 0.0           
            }
        }

        new_user = await self.user_repo.create_user(user_dict)

        return {
            "id": str(new_user["_id"]),
            "email": new_user["email"],
            "role": new_user["role"],
            "status": new_user["status"]
        }

    async def authenticate_user(self, email: str, password: str) -> dict:
        user = await self.user_repo.get_user_by_email(email)

        if not user or not security.verify_password(password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        if user.get("status") == StatusEnum.blocked.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been blocked"
            )

        token_data = {"sub": user["email"], "role": user["role"]}
        access_token = security.create_access_token(data=token_data)
        refresh_token = security.create_refresh_token(data={"sub": user["email"]})

        refresh_hash = security.get_token_hash(refresh_token)
        await self.user_repo.update_refresh_token(user["email"], refresh_hash)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def refresh_session(self, refresh_token: str) -> dict:
        payload = security.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        email = payload.get("sub")
        user = await self.user_repo.get_user_by_email(email)

        if not user or user.get("status") == StatusEnum.blocked.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        saved_hash = user.get("hashed_refresh_token")

        if not saved_hash or security.get_token_hash(refresh_token) != saved_hash:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="The token has been revoked or is invalid.")

        token_data = {"sub": user["email"], "role": user["role"]}
        new_access_token = security.create_access_token(data=token_data)
        new_refresh_token = security.create_refresh_token(data={"sub": user["email"]})

        new_refresh_hash = security.get_token_hash(new_refresh_token)
        await self.user_repo.update_refresh_token(user["email"], new_refresh_hash)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    async def logout(self, refresh_token: str) -> None:
        payload = security.decode_token(refresh_token)

        if payload and payload.get("type") == "refresh":
            email = payload.get("sub")
            if email:
                await self.user_repo.update_refresh_token(email, None)
