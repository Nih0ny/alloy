from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

class ReviewRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["reviews"]

    async def create_review(self, review_data: dict) -> dict:
        result = await self.collection.insert_one(review_data)
        review_data["_id"] = result.inserted_id
        return review_data

    async def get_by_id(self, review_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(review_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_existing_review(
        self, event_id: str, reviewer_id: str, reviewee_id: str
    ) -> Optional[dict]:
        return await self.collection.find_one({
            "event_id": event_id,
            "reviewer_id": reviewer_id,
            "reviewee_id": reviewee_id
        })

    async def calculate_average_rating(self, reviewee_id: str) -> float:
        pipeline = [
            {"$match": {"reviewee_id": reviewee_id}},
            {"$group": {"_id": "$reviewee_id", "avg_rating": {"$avg": "$rating"}}}
        ]
        cursor = self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        if not result or result[0].get("avg_rating") is None:
            return 0.0
        return round(float(result[0]["avg_rating"]), 2)

    async def get_reviews_by_event(self, event_id: str) -> List[dict]:
        cursor = self.collection.find({"event_id": event_id}).sort("created_at", -1)
        return await cursor.to_list(length=200)

    async def get_reviews_for_user(self, reviewee_id: str) -> List[dict]:
        cursor = self.collection.find({"reviewee_id": reviewee_id}).sort("created_at", -1)
        return await cursor.to_list(length=200)
