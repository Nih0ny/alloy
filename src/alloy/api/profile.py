from fastapi import APIRouter, Depends, UploadFile, File, status
from fastapi.responses import FileResponse

from alloy.models.profile_schemas import (
    ProfileUpdate,
    MyProfileResponse,
    PublicProfileResponse,
    EmailNotificationsToggle,
)
from alloy.services.profile_service import ProfileService
from alloy.dependencies import get_current_user, get_profile_service


router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])


@router.get("/me", response_model=MyProfileResponse)
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service)
):
    return await profile_service.get_my_profile(current_user)


@router.put("/me", response_model=MyProfileResponse)
async def update_my_profile(
    profile_in: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service)
):
    return await profile_service.update_my_profile(current_user, profile_in)

@router.patch("/me/email-notifications", status_code=status.HTTP_200_OK)
async def toggle_my_email_notifications(
    settings_in: EmailNotificationsToggle,
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service)
):
    return await profile_service.toggle_email_notifications(current_user, settings_in.enabled)

@router.get("/avatar", response_class=FileResponse)
async def get_my_avatar(
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service)
):
    file_path = profile_service.get_avatar_file_path(current_user)
    return FileResponse(file_path)


@router.post("/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service)
):
    avatar_url = await profile_service.upload_avatar(current_user, file)
    return {"message": "Avatar successfully updated", "avatar_url": avatar_url}


@router.delete("/avatar", status_code=status.HTTP_200_OK)
async def delete_avatar(
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service)
):
    current_avatar_url = current_user.get("profile", {}).get("avatar_url")
    await profile_service.delete_avatar(current_user["email"], current_avatar_url)
    return {"message": "Avatar successfully deleted"}


@router.get("/{user_id}", response_model=PublicProfileResponse)
async def get_user_public_profile(
    user_id: str,
    profile_service: ProfileService = Depends(get_profile_service)
):
    return await profile_service.get_public_profile(user_id)


@router.get("/{user_id}/avatar", response_class=FileResponse)
async def get_user_avatar(
    user_id: str,
    profile_service: ProfileService = Depends(get_profile_service)
):
    file_path = await profile_service.get_user_avatar_by_id(user_id)
    return FileResponse(file_path)
