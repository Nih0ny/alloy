import asyncio
import argparse
import getpass
import sys
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorClient

from alloy.core.config import settings
from alloy.core.security import get_password_hash
from alloy.models.auth_schemas import RoleEnum, StatusEnum

async def create_admin(email: str):
    print(f"Initializing admin creation: {email}")

    password = getpass.getpass("Enter password: ")
    password_confirm = getpass.getpass("Confirm password: ")

    if password != password_confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        sys.exit(1)

    print("Connecting to the database...")
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    db = client[settings.DATABASE_NAME]
    users_collection = db["users"]

    existing_user = await users_collection.find_one({"email": email})
    if existing_user:
        print(f"Error: User with email '{email}' already exists.")
        client.close()
        sys.exit(1)

    print("Hashing password...")
    hashed_password = get_password_hash(password)
    now = datetime.now(UTC)

    admin_doc = {
        "email": email,
        "hashed_password": hashed_password,
        "role": RoleEnum.admin.value,
        "status": StatusEnum.active.value,
        "oauth_provider": None,
        "profile": {
            "full_name": "Main Administrator",
            "phone": None,
            "avatar_url": None,
            "description": "Platform Administrator",
            "rating": 0.0
        },
        "created_at": now,
        "updated_at": now
    }

    await users_collection.insert_one(admin_doc)
    print(f"Success: Administrator account '{email}' has been successfully created!")
    
    client.close()

def main():
    parser = argparse.ArgumentParser(description="System Administrator Creation Utility")
    parser.add_argument("email", type=str, help="Email address of the new administrator")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email))

if __name__ == "__main__":
    main()
