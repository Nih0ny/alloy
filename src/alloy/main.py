import os
from datetime import datetime, UTC
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from alloy.core.config import settings
from alloy.api import auth, profile, events, applications, reviews, categories

DEFAULT_CATEGORIES = ["Animals", "War", "IDPs", "Ecology", "Elderly Care"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    app.state.mongo_client = client

    db = client[settings.DATABASE_NAME]
    await db["users"].create_index("email", unique=True)
    await db["events"].create_index([("status", 1), ("moderation_status", 1)])
    await db["events"].create_index("organizer_id")
    await db["events"].create_index("category_id")

    await db["applications"].create_index(
        [("event_id", 1), ("volunteer_id", 1)],
        unique=True
    )
    await db["applications"].create_index("volunteer_id")

    await db["reviews"].create_index(
        [("event_id", 1), ("reviewer_id", 1), ("reviewee_id", 1)],
        unique=True
    )
    await db["reviews"].create_index("reviewee_id")

    await db["categories"].create_index("name", unique=True)
    if await db["categories"].count_documents({}) == 0:
        now = datetime.now(UTC)
        await db["categories"].insert_many([
            {"name": name, "is_archived": False, "created_at": now, "updated_at": now}
            for name in DEFAULT_CATEGORIES
        ])

    os.makedirs("uploads/avatars", exist_ok=True)
    os.makedirs("uploads/events", exist_ok=True)

    yield
    app.state.mongo_client.close()

app = FastAPI(lifespan=lifespan)

app.mount("/static/avatars", StaticFiles(directory="uploads/avatars"), name="avatars")
app.mount("/static/events", StaticFiles(directory="uploads/events"), name="event_photos")

@app.get("/api/v1/hello-world", description="Route for health check")
async def hello_world():
    return "Hello, World!"

@app.get("/api/v1/db-hello-world", description="Route for DB health check")
async def db_hello_world(request: Request):
    db = request.app.state.mongo_client[settings.DATABASE_NAME]
    
    msg = await db["health_check"].find().to_list(length=1)
    msg[0]["_id"] = str(msg[0]["_id"])

    return msg

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(events.router)
app.include_router(applications.router)
app.include_router(reviews.router)
app.include_router(categories.router)

