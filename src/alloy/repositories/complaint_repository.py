from datetime import datetime, UTC
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

class ComplaintRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["complaints"]
        self.users_collection = db["users"]
        self.events_collection = db["events"]
        self.apps_collection = db["applications"]

    async def create_complaint(self, complaint_data: dict) -> dict:
        result = await self.collection.insert_one(complaint_data)
        complaint_data["_id"] = result.inserted_id
        return complaint_data

    async def get_by_id(self, complaint_id: str) -> Optional[dict]:
        try:
            obj_id = ObjectId(complaint_id)
        except InvalidId:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def get_all_complaints(self, status_filter: Optional[str] = None) -> List[dict]:
        query = {"status": status_filter} if status_filter else {}
        cursor = self.collection.find(query).sort("created_at", -1)
        return await cursor.to_list(length=300)

    async def update_complaint(self, complaint_id: str, update_data: dict) -> Optional[dict]:
        try:
            obj_id = ObjectId(complaint_id)
        except InvalidId:
            return None
        await self.collection.update_one({"_id": obj_id}, {"$set": update_data})
        return await self.get_by_id(complaint_id)

    async def get_all_users_registry(
        self, role_filter: Optional[str] = None, status_filter: Optional[str] = None
    ) -> List[dict]:
        query: dict = {}
        if role_filter:
            query["role"] = role_filter
        if status_filter:
            query["status"] = status_filter

        cursor = self.users_collection.find(query).sort("_id", -1)
        return await cursor.to_list(length=500)

    async def apply_user_block_cascade(
        self, user_id: str, reason: str, complaint_id: Optional[str] = None
    ) -> None:
        now = datetime.now(UTC)
        user_obj_id = ObjectId(user_id)

        await self.users_collection.update_one(
            {"_id": user_obj_id},
            {
                "$set": {
                    "status": "Blocked",
                    "hashed_refresh_token": None,
                    "block_reason": reason,
                    "blocked_at": now
                }
            }
        )

        active_org_events_cursor = self.events_collection.find({
            "organizer_id": user_id,
            "status": {"$in": ["Pending moderation", "Open", "In progress"]}
        })
        active_org_events = await active_org_events_cursor.to_list(length=500)
        org_event_ids = [str(e["_id"]) for e in active_org_events]

        if org_event_ids:
            await self.events_collection.update_many(
                {"organizer_id": user_id, "status": {"$in": ["Pending moderation", "Open", "In progress"]}},
                {"$set": {"status": "Cancelled", "updated_at": now}}
            )
            await self.apps_collection.update_many(
                {"event_id": {"$in": org_event_ids}, "status": {"$in": ["Pending", "Approved"]}},
                {"$set": {"status": "Rejected", "rejection_reason": "Organizer is blocked", "updated_at": now}}
            )

        active_vol_apps_cursor = self.apps_collection.find({
            "volunteer_id": user_id,
            "status": {"$in": ["Pending", "Approved"]}
        })
        active_vol_apps = await active_vol_apps_cursor.to_list(length=500)

        for app in active_vol_apps:
            was_approved = app["status"] == "Approved"
            await self.apps_collection.update_one(
                {"_id": app["_id"]},
                {"$set": {"status": "Withdrawn", "updated_at": now}}
            )
            if was_approved and ObjectId.is_valid(app["event_id"]):
                ev_obj_id = ObjectId(app["event_id"])
                event = await self.events_collection.find_one({"_id": ev_obj_id})
                if event:
                    new_count = max(0, event.get("approved_volunteers_count", 1) - 1)
                    quota = event.get("volunteer_quota", 1)
                    update_fields: dict = {"approved_volunteers_count": new_count, "updated_at": now}
                    if event.get("status") == "In progress" and new_count < quota:
                        update_fields["status"] = "Open"
                    await self.events_collection.update_one({"_id": ev_obj_id}, {"$set": update_fields})

        if complaint_id and ObjectId.is_valid(complaint_id):
            await self.collection.update_one(
                {"_id": ObjectId(complaint_id)},
                {"$set": {"status": "Resolved", "resolved_at": now}}
            )
