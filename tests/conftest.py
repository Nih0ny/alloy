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
def event_create_data(client, admin_headers):
    cat_res = client.post("/api/v1/categories", json={"name": "General"}, headers=admin_headers)
    valid_cat_id = cat_res.json()["id"]

    return {
        "title": "Clean up the central park",
        "description": "We are gathering to clean up the central park from garbage. Join us! Minimum 50 characters here so it passes validation.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {
            "address": "Central Park, Main Entrance",
            "latitude": 49.42298,
            "longitude": 26.98713
        },
        "volunteer_quota": 10,
        "category_id": valid_cat_id  
    }

@pytest.fixture
def create_user(client):
    def _create(email, role):
        data = {
            "email": email,
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "role": role,
            "agreed_to_rules": True
        }
        client.post("/api/v1/auth/register", json=data)
        res = client.post("/api/v1/auth/login", data={"username": email, "password": "StrongPassword123!"})
        return {"Authorization": f"Bearer {res.json().get('access_token')}"}
    return _create

@pytest.fixture
def vol1_headers(create_user):
    return create_user("vol1@example.com", "Volunteer")

@pytest.fixture
def vol2_headers(create_user):
    return create_user("vol2@example.com", "Volunteer")

@pytest.fixture
def org_headers(create_user):
    return create_user("org1@example.com", "Organizer")

@pytest.fixture
def org1_headers(create_user):
    return create_user("org1@example.com", "Organizer")

@pytest.fixture
def org2_headers(create_user):
    return create_user("org2@example.com", "Organizer")

@pytest.fixture
def active_event_id(client, org1_headers, admin_headers):
    event_data = {
        "title": "Park Cleanup Event for Testing",
        "description": "We are gathering to clean up the central park from garbage. Join us! Minimum 50 characters here so it passes validation.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {
            "address": "Central Park, Main Entrance",
            "latitude": 49.42298,
            "longitude": 26.98713
        },
        "volunteer_quota": 5
    }
    res = client.post("/api/v1/events", json=event_data, headers=org1_headers)
    ev_id = res.json()["id"]

    client.patch(f"/api/v1/events/{ev_id}/moderation", json={"action": "Approved"}, headers=admin_headers)
    client.patch(f"/api/v1/events/{ev_id}/status", json={"status": "Open"}, headers=org1_headers)
    return ev_id

@pytest.fixture
def test_application_id(client, vol1_headers, active_event_id):
    payload = {
        "motivation_letter": "I really want to help out!",
        "agreed_to_share_contacts": True
    }
    res = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=vol1_headers)
    return res.json()["id"]

@pytest.fixture
def review_context(client, create_user, admin_headers):
    org_headers = create_user("org_review@example.com", "Organizer")
    vol_headers = create_user("vol_review@example.com", "Volunteer")
    
    org_profile_res = client.get("/api/v1/profile/me", headers=org_headers)
    org_id = org_profile_res.json()["id"]
    
    vol_profile_res = client.get("/api/v1/profile/me", headers=vol_headers)
    vol_id = vol_profile_res.json()["id"]

    event_data = {
        "title": "Post-event review test",
        "description": "Valid description length 50 chars for review testing.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {"address": "Test location", "latitude": 49.0, "longitude": 26.0},
        "volunteer_quota": 2
    }
    event_res = client.post("/api/v1/events", json=event_data, headers=org_headers)
    event_id = event_res.json()["id"]

    client.patch(f"/api/v1/events/{event_id}/moderation", json={"action": "Approved"}, headers=admin_headers)
    client.patch(f"/api/v1/events/{event_id}/status", json={"status": "Open"}, headers=org_headers)

    app_res = client.post(f"/api/v1/events/{event_id}/applications", json={"agreed_to_share_contacts": True}, headers=vol_headers)
    app_id = app_res.json()["id"]
    client.patch(f"/api/v1/applications/{app_id}/review", json={"status": "Approved"}, headers=org_headers)
    
    client.patch(f"/api/v1/events/{event_id}/status", json={"status": "Completed"}, headers=org_headers)

    return {
        "org_headers": org_headers,
        "vol_headers": vol_headers,
        "org_id": org_id,
        "vol_id": vol_id,
        "event_id": event_id
    }

@pytest.fixture
def comm_admin_headers(client, mock_db):
    admin_doc = {
        "email": "admin_comm@example.com",
        "hashed_password": security.get_password_hash("StrongPassword123!"), 
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
    
    res = client.post("/api/v1/auth/login", data={"username": "admin_comm@example.com", "password": "StrongPassword123!"})
    if res.status_code != 200:
        client.post("/api/v1/auth/register", json={
            "email": "admin_comm@example.com", "password": "StrongPassword123!", "password_confirm": "StrongPassword123!", "role": "Admin", "agreed_to_rules": True
        })
        res = client.post("/api/v1/auth/login", data={"username": "admin_comm@example.com", "password": "StrongPassword123!"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

@pytest.fixture
def comm_users(client, create_user, mock_db):
    org_headers = create_user("org_comm@example.com", "Organizer")
    vol1_headers = create_user("vol1_comm@example.com", "Volunteer")
    vol2_headers = create_user("vol2_comm@example.com", "Volunteer")
    blocked_headers = create_user("blocked_comm@example.com", "Volunteer")
    
    org_id = client.get("/api/v1/profile/me", headers=org_headers).json()["id"]
    vol1_id = client.get("/api/v1/profile/me", headers=vol1_headers).json()["id"]
    vol2_id = client.get("/api/v1/profile/me", headers=vol2_headers).json()["id"]
    blocked_id = client.get("/api/v1/profile/me", headers=blocked_headers).json()["id"]

    asyncio.run(mock_db["users"].update_one(
        {"email": "blocked_comm@example.com"},
        {"$set": {"status": "Blocked"}}
    ))

    return {
        "org": org_headers,
        "vol1": vol1_headers,
        "vol2": vol2_headers,
        "blocked": blocked_headers,
        "org_id": org_id,
        "vol1_id": vol1_id,
        "vol2_id": vol2_id,
        "blocked_id": blocked_id
    }

@pytest.fixture
def comm_events(client, comm_users, comm_admin_headers):
    event_data = {
        "title": "Communication Open Event",
        "description": "Valid description length 50 chars for testing communication.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {"address": "Comm Test Address", "latitude": 49.0, "longitude": 26.0},
        "volunteer_quota": 5
    }
    res_open = client.post("/api/v1/events", json=event_data, headers=comm_users["org"])
    open_id = res_open.json()["id"]
    client.patch(f"/api/v1/events/{open_id}/moderation", json={"action": "Approved"}, headers=comm_admin_headers)
    client.patch(f"/api/v1/events/{open_id}/status", json={"status": "Open"}, headers=comm_users["org"])

    event_data["title"] = "Communication Closed Event"
    res_closed = client.post("/api/v1/events", json=event_data, headers=comm_users["org"])
    closed_id = res_closed.json()["id"]
    client.patch(f"/api/v1/events/{closed_id}/moderation", json={"action": "Approved"}, headers=comm_admin_headers)
    client.patch(f"/api/v1/events/{closed_id}/status", json={"status": "Completed"}, headers=comm_users["org"])

    return {"open_id": open_id, "closed_id": closed_id}

@pytest.fixture
def users_for_complaints(client, create_user):
    org_headers = create_user("org_comp@example.com", "Organizer")
    vol_headers = create_user("vol_comp@example.com", "Volunteer")
    
    org_id = client.get("/api/v1/profile/me", headers=org_headers).json()["id"]
    vol_id = client.get("/api/v1/profile/me", headers=vol_headers).json()["id"]
    
    return {
        "org_headers": org_headers,
        "vol_headers": vol_headers,
        "org_id": org_id,
        "vol_id": vol_id
    }

@pytest.fixture
def target_event(client, users_for_complaints, admin_headers):
    event_data = {
        "title": "Event for complaints",
        "description": "Valid description length 50 chars for testing communication.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {"address": "Test Address", "latitude": 49.0, "longitude": 26.0},
        "volunteer_quota": 5
    }
    res = client.post("/api/v1/events", json=event_data, headers=users_for_complaints["org_headers"])
    event_id = res.json()["id"]

    mod_res = client.patch(
        f"/api/v1/events/{event_id}/moderation", 
        json={"action": "Approved"}, 
        headers=admin_headers
    )
    
    return event_id

@pytest.fixture
def target_comment(client, target_event, users_for_complaints):
    res = client.post(
        f"/api/v1/events/{target_event}/comments",
        json={"text": "This is a spam comment that needs to be reported"},
        headers=users_for_complaints["vol_headers"]
    )
    return res.json()["id"]

@pytest.fixture
def sample_complaint(client, users_for_complaints, target_event):
    payload = {
        "target_type": "Event",
        "target_id": target_event,
        "violation_category": "Spam",
        "description": "This event seems to be a scam or spam."
    }
    res = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["vol_headers"])
    return res.json()["id"]
