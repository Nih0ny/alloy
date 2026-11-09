from datetime import datetime, UTC
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

class NotificationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["notifications"]

    async def create_notification(self, notif_data: dict) -> dict:
        result = await self.collection.insert_one(notif_data)
        notif_data["_id"] = result.inserted_id
        return notif_data

    async def create_many_notifications(self, notif_list: List[dict]) -> None:
        if notif_list:
            await self.collection.insert_many(notif_list)

    async def get_user_notifications(
        self, user_id: str, unread_only: bool = False, skip: int = 0, limit: int = 50
    ) -> List[dict]:
        query: dict = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_unread(self, user_id: str) -> int:
        return await self.collection.count_documents({"user_id": user_id, "is_read": False})

    async def mark_as_read(self, notification_id: str, user_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(notification_id)
        except InvalidId:
            return None
        await self.collection.update_one(
            {"_id": obj_id, "user_id": user_id},
            {"$set": {"is_read": True, "read_at": datetime.now(UTC)}}
        )
        return await self.collection.find_one({"_id": obj_id})

    async def mark_all_as_read(self, user_id: str) -> int:
        result = await self.collection.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True, "read_at": datetime.now(UTC)}}
        )
        return result.modified_count
