import asyncio
import pytest
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from alloy.main import app
from alloy.dependencies import get_database  
from alloy.core import security

@pytest.fixture
def mock_db():
    mock_client = AsyncMongoMockClient()
    db = mock_client["test_mock_database"]
    
    return db

@pytest.fixture
def client(mock_db):
    def override_get_db():
        yield mock_db
        
    app.dependency_overrides[get_database] = override_get_db
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()

@pytest.fixture
def valid_user_data():
    return {
        "email": "test.volunteer@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "role": "Volunteer",
        "agreed_to_rules": True
    }

@pytest.fixture
def login_data(valid_user_data):
    return {
        "username": valid_user_data["email"],
        "password": valid_user_data["password"]
    }

@pytest.fixture
def auth_headers(client, valid_user_data, login_data):
    client.post("/api/v1/auth/register", json=valid_user_data)
    response = client.post("/api/v1/auth/login", data=login_data)
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_image_file():
    return {"file": ("avatar.png", b"dummy image data", "image/png")}

@pytest.fixture
def volunteer_data():
    return {
        "email": "volunteer@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "role": "Volunteer",
        "agreed_to_rules": True
    }

@pytest.fixture
def organizer_data():
    return {
        "email": "organizer@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "role": "Organizer",
        "agreed_to_rules": True
    }

@pytest.fixture
def another_organizer_data():
    return {
        "email": "organizer2@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "role": "Organizer",
        "agreed_to_rules": True
    }

@pytest.fixture
def admin_data():
    return {
        "email": "admin@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "role": "Admin",
        "agreed_to_rules": True
    }

@pytest.fixture
def volunteer_headers(client, volunteer_data):
    client.post("/api/v1/auth/register", json=volunteer_data)
    res = client.post("/api/v1/auth/login", data={"username": volunteer_data["email"], "password": volunteer_data["password"]})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

@pytest.fixture
def organizer_headers(client, organizer_data):
    client.post("/api/v1/auth/register", json=organizer_data)
    res = client.post("/api/v1/auth/login", data={"username": organizer_data["email"], "password": organizer_data["password"]})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

@pytest.fixture
def another_organizer_headers(client, another_organizer_data):
    client.post("/api/v1/auth/register", json=another_organizer_data)
    res = client.post("/api/v1/auth/login", data={"username": another_organizer_data["email"], "password": another_organizer_data["password"]})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

@pytest.fixture
def admin_headers(client, mock_db, admin_data):
    admin_doc = {
        "email": admin_data["email"],
        "hashed_password": security.get_password_hash(admin_data["password"]), 
        "role": "Admin",
        "status": "Active",
        "oauth_provider": None,
        "profile": {
            "full_name": "Main Administrator",
            "phone": None,
            "avatar_url": None,
            "description": "Platform Administrator",
            "rating": 0.0
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    asyncio.run(mock_db["users"].insert_one(admin_doc))

    res = client.post(
        "/api/v1/auth/login", 
        data={"username": admin_data["email"], "password": admin_data["password"]}
    )
    
    assert res.status_code == 200, "Failed to log in test admin"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

@pytest.fixture
def event_create_data():
    return {
        "title": "Clean up the central park",
        "description": "We are gathering to clean up the central park from garbage. Join us! Minimum 50 characters here so it passes validation.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {
            "address": "Central Park, Main Entrance",
            "latitude": 49.42298,
            "longitude": 26.98713
        },
        "volunteer_quota": 10
    }
