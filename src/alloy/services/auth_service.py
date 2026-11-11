import asyncio
import logging
import secrets
import httpx2
from fastapi import HTTPException, status

from alloy.repositories.user_repository import UserRepository
from alloy.services.notification_service import NotificationService
from alloy.models.notification_schemas import NotificationTypeEnum
from alloy.models.auth_schemas import (
    UserCreate,
    StatusEnum,
    OAuthProviderEnum,
    OAuthLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordConfirmRequest,
)
from alloy.core import security
from alloy.core.config import settings

logger = logging.getLogger("alloy.auth")

class AuthService:
    def __init__(self, user_repo: UserRepository, notif_service: NotificationRepository):
        self.user_repo = user_repo
        self.notif_service = notif_service

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
                detail="A user with this email already exists"
            )

        hashed_password = security.get_password_hash(user_in.password)
        user_dict = {
            "email": user_in.email,
            "hashed_password": hashed_password,
            "role": user_in.role.value,
            "status": StatusEnum.active.value,
            "is_email_verified": False,
            "hashed_verification_token": None,
            "oauth_provider": None,
            "profile": {
                "full_name": None,
                "phone": None,
                "avatar_url": None,
                "description": None,
                "rating": 0.0,
                "email_notifications_enabled": True
            }
        }

        new_user = await self.user_repo.create_user(user_dict)

        await self._send_verification_email(new_user["email"])

        tokens = await self._issue_tokens_for_user(new_user)

        return {
            "id": str(new_user["_id"]),
            "email": new_user["email"],
            "role": new_user["role"],
            "status": new_user["status"],
            "is_email_verified": False,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer"
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

            user_name = user.get("profile", {}).get("full_name") or "User"
            subject = "Password Reset — Alloy Platform"
            body = (
                f"Hello, {user_name}!\n\n"
                f"You have requested a password reset in the Alloy mobile application.\n"
                f"Your one-time code (token) for password reset is:\n\n"
                f"{reset_token}\n\n"
                f"Mobile application link (Deep Link):\n"
                f"alloy://reset-password?code={reset_token}\n\n"
                f"This code is valid for {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
                f"If you did not request this, simply ignore this email."
            )

            asyncio.create_task(
                self.notif_service.send_email_async(
                    to_email=user["email"],
                    subject=subject,
                    body=body
                )
            )

            logger.info(
                "PASSWORD_RESET_EMAIL_QUEUED",
                extra={"event_type": "security_audit", "recipient": user["email"]}
            )

        return {
            "detail": "If an account with the specified email exists, password reset instructions have been sent to your Email."
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

        await self.notif_service.notify_user(
            user_id=str(user["_id"]),
            notif_type=NotificationTypeEnum.account_security,
            title="Password Successfully Changed",
            message="Your account password has been successfully reset and updated.",
            email_to=user["email"]
        )

        return {"detail": "Password successfully updated. You can now log in with the new password."}

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
            if not oauth_in.role:
                raise HTTPException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    detail="To complete the first registration via OAuth, you must select a role ('Volunteer' or 'Organizer')"
                )
            if not oauth_in.agreed_to_rules:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You must agree to the platform rules"
                )

            random_password_hash = security.get_password_hash(secrets.token_urlsafe(32))
            user_dict = {
                "email": email,
                "hashed_password": random_password_hash,
                "role": oauth_in.role.value,
                "status": StatusEnum.active.value,
                "oauth_provider": provider.value,
                "profile": {
                    "full_name": social_data.get("full_name"),
                    "phone": None,
                    "avatar_url": social_data.get("avatar_url"),
                    "description": None,
                    "rating": 0.0,
                    "email_notifications_enabled": True
                }
            }
            user = await self.user_repo.create_user(user_dict)

        return await self._issue_tokens_for_user(user)

    async def _send_verification_email(self, email: str) -> None:
        verification_token = security.create_email_verification_token(email)
        verification_hash = security.get_token_hash(verification_token)
        await self.user_repo.set_email_verification_token(email, verification_hash)

        subject = "Email Verification — Alloy Platform"
        body = (
            f"Welcome to the Alloy local mutual aid platform!\n\n"
            f"To verify your email address, use this code in the app:\n\n"
            f"{verification_token}\n\n"
            f"Or follow the direct link (Deep Link):\n"
            f"alloy://verify-email?token={verification_token}\n\n"
            f"The link is valid for {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours."
        )

        asyncio.create_task(
            self.notif_service.send_email_async(
                to_email=email,
                subject=subject,
                body=body
            )
        )

        logger.info(
            "EMAIL_VERIFICATION_SENT",
            extra={"event_type": "security_audit", "recipient": email}
        )

    async def verify_email(self, token: str) -> dict:
        payload = security.decode_token(token)
        if not payload or payload.get("type") != "email_verification":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired email verification token"
            )

        email = payload.get("sub")
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.get("is_email_verified"):
            return {"detail": "Email has already been verified."}

        saved_hash = user.get("hashed_verification_token")
        if not saved_hash or security.get_token_hash(token) != saved_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification code is no longer valid or a newer one has been generated"
            )

        await self.user_repo.mark_email_as_verified(email)

        await self.notif_service.notify_user(
            user_id=str(user["_id"]),
            notif_type=NotificationTypeEnum.account_security,
            title="Email successfully verified!",
            message="Your email has been verified. You now have access to all features of the Alloy platform."
        )

        logger.info(
            "EMAIL_VERIFIED_SUCCESSFULLY",
            extra={"event_type": "security_audit", "user_id": str(user["_id"]), "recipient": email}
        )
        return {"detail": "Email successfully verified!"}


    async def resend_verification_email(self, email: str) -> dict:
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            return {"detail": "If the account exists and is not yet verified, an email with the code has been resent."}

        if user.get("status") == StatusEnum.blocked.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")

        if user.get("is_email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already verified"
            )

        await self._send_verification_email(email)
        return {"detail": "Email verification letter has been successfully resent."}
