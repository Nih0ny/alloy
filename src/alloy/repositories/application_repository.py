from datetime import datetime, UTC
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId


class ApplicationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["applications"]

    async def create_application(self, app_data: dict) -> dict:
        result = await self.collection.insert_one(app_data)
        app_data["_id"] = result.inserted_id
        return app_data

    async def get_by_id(self, application_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(application_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_by_event_and_volunteer(self, event_id: str, volunteer_id: str) -> Optional[dict]:
        return await self.collection.find_one({
            "event_id": event_id,
            "volunteer_id": volunteer_id
        })

    async def get_by_event(self, event_id: str) -> List[dict]:
        cursor = self.collection.find({"event_id": event_id}).sort("created_at", 1)
        return await cursor.to_list(length=200)

    async def get_by_volunteer(self, volunteer_id: str) -> List[dict]:
        cursor = self.collection.find({"volunteer_id": volunteer_id}).sort("created_at", -1)
        return await cursor.to_list(length=200)

    async def update_application(self, application_id: str, update_data: dict) -> Optional[dict]:
        try:
            obj_id = ObjectId(application_id)
        except InvalidId:
            return None

        update_data["updated_at"] = datetime.now(UTC)
        await self.collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        return await self.get_by_id(application_id)
