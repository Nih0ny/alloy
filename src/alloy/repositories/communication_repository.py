from datetime import datetime, UTC
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId


class CommentRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["comments"]

    async def create_comment(self, comment_data: dict) -> dict:
        result = await self.collection.insert_one(comment_data)
        comment_data["_id"] = result.inserted_id
        return comment_data

    async def get_by_id(self, comment_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(comment_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_by_event(self, event_id: str, skip: int = 0, limit: int = 100) -> List[dict]:
        cursor = self.collection.find({"event_id": event_id}).sort("created_at", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def delete_comment(self, comment_id: str) -> bool:
        try:
            obj_id = ObjectId(comment_id)
        except InvalidId:
            return False
        result = await self.collection.delete_one({"_id": obj_id})
        return result.deleted_count > 0


class MessageRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["messages"]

    async def create_message(self, msg_data: dict) -> dict:
        result = await self.collection.insert_one(msg_data)
        msg_data["_id"] = result.inserted_id
        return msg_data

    async def get_conversation_messages(
        self, user_a_id: str, user_b_id: str, skip: int = 0, limit: int = 100
    ) -> List[dict]:
        query = {
            "$or": [
                {"sender_id": user_a_id, "recipient_id": user_b_id},
                {"sender_id": user_b_id, "recipient_id": user_a_id}
            ]
        }
        cursor = self.collection.find(query).sort("created_at", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def mark_conversation_as_read(self, current_user_id: str, sender_id: str) -> None:
        await self.collection.update_many(
            {"sender_id": sender_id, "recipient_id": current_user_id, "is_read": False},
            {"$set": {"is_read": True}}
        )

    async def get_user_messages_all(self, user_id: str) -> List[dict]:
        cursor = self.collection.find({
            "$or": [{"sender_id": user_id}, {"recipient_id": user_id}]
        }).sort("created_at", -1)
        return await cursor.to_list(length=500)


class SupportRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["support_tickets"]

    async def create_ticket(self, ticket_data: dict) -> dict:
        result = await self.collection.insert_one(ticket_data)
        ticket_data["_id"] = result.inserted_id
        return ticket_data

    async def get_by_id(self, ticket_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(ticket_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_tickets_by_user(self, user_id: str) -> List[dict]:
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", -1)
        return await cursor.to_list(length=100)

    async def get_all_tickets(self, status_filter: Optional[str] = None) -> List[dict]:
        query = {"status": status_filter} if status_filter else {}
        cursor = self.collection.find(query).sort("created_at", -1)
        return await cursor.to_list(length=200)

    async def update_ticket(self, ticket_id: str, update_data: dict) -> Optional[dict]:
        try:
            obj_id = ObjectId(ticket_id)
        except InvalidId:
            return None
        update_data["updated_at"] = datetime.now(UTC)
        await self.collection.update_one({"_id": obj_id}, {"$set": update_data})
        return await self.get_by_id(ticket_id)
