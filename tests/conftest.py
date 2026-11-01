import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from alloy.main import app
from alloy.dependencies import get_database  

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
