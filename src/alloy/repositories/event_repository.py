from typing import List, Optional
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId


class EventRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["events"]

    async def create_event(self, event_data: dict) -> dict:
        result = await self.collection.insert_one(event_data)
        event_data["_id"] = result.inserted_id
        return event_data

    async def get_event_by_id(self, event_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(event_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_public_events(
        self,
        search_query: Optional[str] = None,
        categories: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        query: dict = {
            "status": "Open",
            "moderation_status": "Approved"
        }

        if categories:
            query["category_id"] = {"$in": categories}

        if search_query:
            query["$or"] = [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"description": {"$regex": search_query, "$options": "i"}}
            ]

        cursor = self.collection.find(query).sort("event_date", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_events_by_organizer(self, organizer_id: str) -> List[dict]:
        cursor = self.collection.find({"organizer_id": organizer_id}).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def get_pending_moderation_events(self) -> List[dict]:
        cursor = self.collection.find({"moderation_status": "Pending"}).sort("created_at", 1)
        return await cursor.to_list(length=100)

    async def update_event(self, event_id: str, update_data: dict) -> Optional[dict]:
        try:
            obj_id = ObjectId(event_id)
        except InvalidId:
            return None

        update_data["updated_at"] = datetime.now(UTC)
        await self.collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        return await self.get_event_by_id(event_id)

    async def add_event_photos(self, event_id: str, photo_urls: List[str]) -> Optional[dict]:
        try:
            obj_id = ObjectId(event_id)
        except InvalidId:
            return None

        await self.collection.update_one(
            {"_id": obj_id},
            {
                "$push": {"photos": {"$each": photo_urls}},
                "$set": {"updated_at": datetime.now(UTC)}
            }
        )
        return await self.get_event_by_id(event_id)

    async def delete_event(self, event_id: str) -> bool:
        try:
            obj_id = ObjectId(event_id)
        except InvalidId:
            return False
        result = await self.collection.delete_one({"_id": obj_id})
        return result.deleted_count > 0

    async def cancel_active_applications_for_event(self, event_id: str) -> None:
        await self.db["applications"].update_many(
            {
                "event_id": event_id,
                "status": {"$in": ["Pending", "Approved"]}
            },
            {
                "$set": {
                    "status": "Rejected",
                    "updated_at": datetime.now(UTC)
                }
            }
        )

    async def increment_approved_volunteers(
        self, event_id: str, delta: int, new_status: Optional[str] = None
    ) -> Optional[dict]:
        try:
            obj_id = ObjectId(event_id)
        except InvalidId:
            return None

        update_doc: dict = {
            "$inc": {"approved_volunteers_count": delta},
            "$set": {"updated_at": datetime.now(UTC)}
        }
        if new_status:
            update_doc["$set"]["status"] = new_status

        await self.collection.update_one({"_id": obj_id}, update_doc)
        return await self.get_event_by_id(event_id)
