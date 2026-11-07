import re
from datetime import datetime, UTC
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId


class CategoryRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["categories"]
        self.events_collection = db["events"]

    async def create_category(self, category_data: dict) -> dict:
        result = await self.collection.insert_one(category_data)
        category_data["_id"] = result.inserted_id
        return category_data

    async def get_by_id(self, category_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(category_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_by_name_case_insensitive(self, name: str) -> Optional[dict]:
        escaped_name = re.escape(name.strip())
        return await self.collection.find_one({
            "name": {"$regex": f"^{escaped_name}$", "$options": "i"}
        })

    async def get_all_categories(self, include_archived: bool = False) -> List[dict]:
        query = {} if include_archived else {"is_archived": False}
        cursor = self.collection.find(query).sort("name", 1)
        return await cursor.to_list(length=500)

    async def update_category(self, category_id: str, update_data: dict) -> Optional[dict]:
        try:
            obj_id = ObjectId(category_id)
        except InvalidId:
            return None

        update_data["updated_at"] = datetime.now(UTC)
        await self.collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        return await self.get_by_id(category_id)

    async def delete_category_permanently(self, category_id: str) -> bool:
        try:
            obj_id = ObjectId(category_id)
        except InvalidId:
            return False
        result = await self.collection.delete_one({"_id": obj_id})
        return result.deleted_count > 0

    async def count_events_for_category(self, category_id: str, category_name: str) -> tuple[int, int]:
        category_match = {"$in": [category_id, category_name]}

        total_count = await self.events_collection.count_documents({
            "category_id": category_match
        })

        active_count = await self.events_collection.count_documents({
            "category_id": category_match,
            "status": {"$in": ["Open", "In Progress"]}
        })

        return active_count, total_count
