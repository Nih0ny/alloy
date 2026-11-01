import os
import uuid
import aiofiles
from typing import List
from fastapi import UploadFile, HTTPException, status

from alloy.repositories.user_repository import UserRepository
from alloy.models.profile_schemas import ProfileUpdate

UPLOAD_DIR = "uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class ProfileService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def _build_reviews_list(self, user_id: str) -> List[dict]:
        raw_reviews = await self.user_repo.get_reviews_for_user(user_id)
        formatted_reviews = []

        for rev in raw_reviews:
            author = await self.user_repo.get_user_by_id(rev["reviewer_id"])
            author_name = "User"
            if author:
                author_name = author.get("profile", {}).get("full_name") or author["email"]

            formatted_reviews.append({
                "id": str(rev["_id"]),
                "event_id": rev["event_id"],
                "author_id": rev["reviewer_id"],
                "author_name": author_name,
                "rating": rev["rating"],
                "comment": rev.get("comment"),
                "created_at": rev["created_at"]
            })
        return formatted_reviews

    async def _build_volunteer_tasks_history(self, volunteer_id: str) -> List[dict]:
        applications = await self.user_repo.get_volunteer_applications(volunteer_id)
        tasks_history = []

        for app in applications:
            event = await self.user_repo.get_event_Basic_info(app["event_id"])
            event_title = event["title"] if event else "Deleted event"
            event_status = event["status"] if event else "Cancelled"
            app_status = app["status"]

            can_withdraw = (
                event_status not in ["Completed", "Cancelled"]
                and app_status in ["Pending", "Approved"]
            )

            tasks_history.append({
                "application_id": str(app["_id"]),
                "event_id": app["event_id"],
                "event_title": event_title,
                "event_status": event_status,
                "application_status": app_status,
                "can_withdraw": can_withdraw,
                "applied_at": app["created_at"]
            })
        return tasks_history

    async def get_my_profile(self, current_user: dict) -> dict:
        user_id = str(current_user["_id"])
        profile = current_user.get("profile", {})

        reviews = await self._build_reviews_list(user_id)
        my_tasks = await self._build_volunteer_tasks_history(user_id)

        return {
            "id": user_id,
            "email": current_user["email"],
            "role": current_user["role"],
            "status": current_user["status"],
            "full_name": profile.get("full_name"),
            "phone": profile.get("phone"),
            "avatar_url": profile.get("avatar_url"),
            "description": profile.get("description"),
            "rating": profile.get("rating", 0.0),
            "reviews": reviews,
            "my_tasks": my_tasks
        }

    async def update_my_profile(self, current_user: dict, profile_in: ProfileUpdate) -> dict:
        updated_user = await self.user_repo.update_profile_info(
            current_user["email"],
            profile_in.model_dump()
        )
        return await self.get_my_profile(updated_user)

    async def get_public_profile(self, user_id: str) -> dict:
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        profile = user.get("profile", {})
        reviews = await self._build_reviews_list(user_id)

        return {
            "id": str(user["_id"]),
            "role": user["role"],
            "full_name": profile.get("full_name"),
            "avatar_url": profile.get("avatar_url"),
            "description": profile.get("description"),
            "rating": profile.get("rating", 0.0),
            "reviews": reviews
        }

    def get_avatar_file_path(self, user: dict) -> str:
        avatar_url = user.get("profile", {}).get("avatar_url")
        if not avatar_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not have an avatar set"
            )
        filename = avatar_url.split("/")[-1]
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image file not found on the server"
            )
        return file_path

    async def get_user_avatar_by_id(self, user_id: str) -> str:
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self.get_avatar_file_path(user)

    async def upload_avatar(self, current_user: dict, file: UploadFile) -> str:
        allowed_content_types = ["image/jpeg", "image/png"]
        if file.content_type not in allowed_content_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPG or PNG images are allowed"
            )

        file.file.seek(0, 2)
        file_size = file.file.tell()
        await file.seek(0)

        if file_size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must not exceed 5 MB"
            )

        old_avatar_url = current_user.get("profile", {}).get("avatar_url")
        if old_avatar_url:
            old_filename = old_avatar_url.split("/")[-1]
            old_path = os.path.join(UPLOAD_DIR, old_filename)
            if os.path.exists(old_path):
                os.remove(old_path)

        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)

        avatar_url = f"/static/avatars/{unique_filename}"
        await self.user_repo.update_user_avatar(current_user["email"], avatar_url)
        return avatar_url

    async def delete_avatar(self, email: str, current_avatar_url: str | None) -> None:
        if current_avatar_url:
            filename = current_avatar_url.split("/")[-1]
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        await self.user_repo.update_user_avatar(email, None)
