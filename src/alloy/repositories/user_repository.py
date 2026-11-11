from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["users"]

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        return await self.collection.find_one({"email": email})

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(user_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def create_user(self, user_data: dict) -> dict:
        result = await self.collection.insert_one(user_data)
        user_data["_id"] = result.inserted_id
        return user_data

    async def update_refresh_token(self, email: str, token_hash: Optional[str]) -> None:
        await self.collection.update_one(
            {"email": email},
            {"$set": {"hashed_refresh_token": token_hash}}
        )

    async def update_user_avatar(self, email: str, avatar_url: Optional[str]) -> None:
        await self.collection.update_one(
            {"email": email},
            {"$set": {"profile.avatar_url": avatar_url}}
        )

    async def update_profile_info(self, email: str, profile_data: dict) -> Optional[dict]:
        update_fields = {
            "profile.full_name": profile_data["full_name"],
            "profile.phone": profile_data.get("phone"),
            "profile.description": profile_data.get("description"),
        }
        await self.collection.update_one(
            {"email": email},
            {"$set": update_fields}
        )
        return await self.get_user_by_email(email)

    async def get_reviews_for_user(self, user_id: str) -> List[dict]:
        cursor = self.db["reviews"].find({"reviewee_id": user_id}).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def get_volunteer_applications(self, volunteer_id: str) -> List[dict]:
        cursor = self.db["applications"].find({"volunteer_id": volunteer_id}).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def get_event_Basic_info(self, event_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(event_id)
        except InvalidId:
            return None
        return await self.db["events"].find_one({"_id": obj_id}, {"title": 1, "status": 1})

    async def update_user_rating(self, user_id: str, new_rating: float) -> None:
        try:
            obj_id = ObjectId(user_id)
        except InvalidId:
            return
        await self.collection.update_one(
            {"_id": obj_id},
            {"$set": {"profile.rating": round(new_rating, 2)}}
        )

    async def set_password_reset_token(self, email: str, reset_token_hash: Optional[str]) -> None:
        await self.collection.update_one(
            {"email": email},
            {"$set": {"hashed_reset_token": reset_token_hash}}
        )

    async def update_user_password(self, email: str, new_hashed_password: str) -> None:
        await self.collection.update_one(
            {"email": email},
            {
                "$set": {
                    "hashed_password": new_hashed_password,
                    "hashed_reset_token": None,
                    "hashed_refresh_token": None
                }
            }
        )

    async def sync_oauth_profile_fields(
        self, email: str, provider: str, full_name: Optional[str], avatar_url: Optional[str]
    ) -> Optional[dict]:
        user = await self.get_user_by_email(email)
        if not user:
            return None

        profile = user.get("profile", {})
        update_fields: dict = {"oauth_provider": provider}

        if full_name and not profile.get("full_name"):
            update_fields["profile.full_name"] = full_name
        if avatar_url and not profile.get("avatar_url"):
            update_fields["profile.avatar_url"] = avatar_url

        await self.collection.update_one({"email": email}, {"$set": update_fields})
        return await self.get_user_by_email(email)

    async def set_email_verification_token(
    self, email: str, verification_token_hash: Optional[str]
) -> None:
        await self.collection.update_one(
            {"email": email},
            {"$set": {"hashed_verification_token": verification_token_hash}}
        )


    async def mark_email_as_verified(self, email: str) -> None:
        await self.collection.update_one(
            {"email": email},
            {
                "$set": {
                    "is_email_verified": True,
                    "hashed_verification_token": None
                }
            }
        )
