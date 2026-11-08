from fastapi import APIRouter, Depends, status, Response, Cookie, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from alloy.models.auth_schemas import (
    UserCreate,
    UserResponse,
    Token,
    ForgotPasswordRequest,
    ResetPasswordConfirmRequest,
    OAuthProviderEnum,
    OAuthLoginRequest,
)
from alloy.services.auth_service import AuthService
from alloy.dependencies import get_auth_service
from alloy.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    return await auth_service.register_user(user_in)

@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    tokens = await auth_service.authenticate_user(form_data.username, form_data.password)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return {"access_token": tokens["access_token"], "token_type": tokens["token_type"]}

@router.post("/oauth/{provider}", response_model=Token)
async def oauth_login_or_register(
    provider: OAuthProviderEnum,
    oauth_in: OAuthLoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    tokens = await auth_service.authenticate_oauth(provider, oauth_in)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return {"access_token": tokens["access_token"], "token_type": tokens["token_type"]}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    req: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    return await auth_service.request_password_reset(req)

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    req: ResetPasswordConfirmRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    return await auth_service.confirm_password_reset(req)

@router.post("/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, include_in_schema=False),
    auth_service: AuthService = Depends(get_auth_service)
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing in cookies"
        )

    tokens = await auth_service.refresh_session(refresh_token)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return {"access_token": tokens["access_token"], "token_type": tokens["token_type"]}

@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, include_in_schema=False),
    auth_service: AuthService = Depends(get_auth_service)
):
    if refresh_token:
        await auth_service.logout(refresh_token)

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"detail": "Successful exit"}
