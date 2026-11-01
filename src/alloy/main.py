from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from alloy.core.config import settings
from alloy.api import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    app.state.mongo_client = client

    db = client[settings.DATABASE_NAME]
    await db["users"].create_index("email", unique=True)

    yield
    app.state.mongo_client.close()

app = FastAPI(lifespan=lifespan)

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
