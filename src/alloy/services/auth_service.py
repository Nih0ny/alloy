import logging
import secrets
import httpx2
from fastapi import HTTPException, status

from alloy.repositories.user_repository import UserRepository
from alloy.models.auth_schemas import (
    UserCreate,
    StatusEnum,
    OAuthProviderEnum,
    OAuthLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordConfirmRequest,
)
from alloy.core import security

logger = logging.getLogger("alloy.auth")

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def _issue_tokens_for_user(self, user: dict) -> dict:
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

    async def register_user(self, user_in: UserCreate) -> dict:
        existing_user = await self.user_repo.get_user_by_email(user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )

        hashed_password = security.get_password_hash(user_in.password)
        user_dict = {
            "email": user_in.email,
            "hashed_password": hashed_password,
            "role": user_in.role.value,
            "status": StatusEnum.active.value,
            "oauth_provider": None,
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

        if not user or not user.get("hashed_password") or not security.verify_password(password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if user.get("status") == StatusEnum.blocked.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been blocked by the Administrator"
            )

        return await self._issue_tokens_for_user(user)

    async def refresh_session(self, refresh_token: str) -> dict:
        payload = security.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Refresh token"
            )

        email = payload.get("sub")
        user = await self.user_repo.get_user_by_email(email)

        if not user or user.get("status") == StatusEnum.blocked.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        saved_hash = user.get("hashed_refresh_token")
        if not saved_hash or security.get_token_hash(refresh_token) != saved_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked or is invalid"
            )

        return await self._issue_tokens_for_user(user)

    async def logout(self, refresh_token: str) -> None:
        payload = security.decode_token(refresh_token)
        if payload and payload.get("type") == "refresh":
            email = payload.get("sub")
            if email:
                await self.user_repo.update_refresh_token(email, None)

    async def request_password_reset(self, req: ForgotPasswordRequest) -> dict:
        user = await self.user_repo.get_user_by_email(req.email)
        if user and user.get("status") != StatusEnum.blocked.value:
            reset_token = security.create_password_reset_token(user["email"])
            reset_hash = security.get_token_hash(reset_token)
            await self.user_repo.set_password_reset_token(user["email"], reset_hash)

            logger.info(
                "PASSWORD_RESET_REQUEST | email=%s | reset_token=%s",
                user["email"],
                reset_token
            )

        return {
            "detail": "If an account with the specified email exists, password reset instructions have been sent."
        }

    async def confirm_password_reset(self, req: ResetPasswordConfirmRequest) -> dict:
        payload = security.decode_token(req.reset_token)
        if not payload or payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token"
            )

        email = payload.get("sub")
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        saved_reset_hash = user.get("hashed_reset_token")
        if not saved_reset_hash or security.get_token_hash(req.reset_token) != saved_reset_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset token has already been used or revoked"
            )

        new_hashed_pwd = security.get_password_hash(req.new_password)
        await self.user_repo.update_user_password(email, new_hashed_pwd)

        return {"detail": "Password successfully updated. You can now log in with your new password."}

    async def _fetch_google_user_info(self, token: str) -> dict:
        async with httpx2.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "email": data.get("email"),
                    "full_name": data.get("name"),
                    "avatar_url": data.get("picture")
                }

            resp_id = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": token}
            )
            if resp_id.status_code == 200:
                data = resp_id.json()
                return {
                    "email": data.get("email"),
                    "full_name": data.get("name"),
                    "avatar_url": data.get("picture")
                }

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate Google account (invalid token)"
        )

    async def _fetch_facebook_user_info(self, token: str) -> dict:
        async with httpx2.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://graph.facebook.com/me",
                params={
                    "fields": "id,name,email,picture.type(large)",
                    "access_token": token
                }
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to authenticate Facebook account (invalid token)"
                )

            data = resp.json()
            picture_url = (
                data.get("picture", {}).get("data", {}).get("url")
                if isinstance(data.get("picture"), dict) else None
            )
            return {
                "email": data.get("email"),
                "full_name": data.get("name"),
                "avatar_url": picture_url
            }

    async def authenticate_oauth(
        self, provider: OAuthProviderEnum, oauth_in: OAuthLoginRequest
    ) -> dict:
        if provider == OAuthProviderEnum.google:
            social_data = await self._fetch_google_user_info(oauth_in.token)
        else:
            social_data = await self._fetch_facebook_user_info(oauth_in.token)

        email = social_data.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The {provider.value} service did not provide access to your email"
            )

        user = await self.user_repo.get_user_by_email(email)

        if user:
            if user.get("status") == StatusEnum.blocked.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been blocked by the Administrator"
                )
            user = await self.user_repo.sync_oauth_profile_fields(
                email=email,
                provider=provider.value,
                full_name=social_data.get("full_name"),
                avatar_url=social_data.get("avatar_url")
            )
        else:
            random_password_hash = security.get_password_hash(secrets.token_urlsafe(32))
            user_dict = {
                "email": email,
                "hashed_password": random_password_hash,
                "role": oauth_in.role.value if oauth_in.role else "Volunteer",
                "status": StatusEnum.active.value,
                "oauth_provider": provider.value,
                "profile": {
                    "full_name": social_data.get("full_name"),
                    "phone": None,
                    "avatar_url": social_data.get("avatar_url"),
                    "description": None,
                    "rating": 0.0
                }
            }
            user = await self.user_repo.create_user(user_dict)

        return await self._issue_tokens_for_user(user)
