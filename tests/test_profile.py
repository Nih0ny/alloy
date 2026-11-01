import pytest

@pytest.fixture
def auth_headers(client, valid_user_data, login_data):
    client.post("/api/v1/auth/register", json=valid_user_data)
    response = client.post("/api/v1/auth/login", data=login_data)
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_image_file():
    return {"file": ("avatar.png", b"dummy image data", "image/png")}

def test_get_my_profile_success(client, auth_headers):
    response = client.get("/api/v1/profile/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "role" in data
    assert "email" in data
    assert "status" in data

def test_get_my_profile_unauthorized(client):
    response = client.get("/api/v1/profile/me")
    assert response.status_code == 401

def test_update_my_profile_success(client, auth_headers):
    update_data = {"full_name": "Test User"}
    response = client.put("/api/v1/profile/me", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Test User"

def test_update_my_profile_full(client, auth_headers):
    update_data = {
        "full_name": "Test User Complete",
        "phone": "+380123456789",
        "description": "Test description"
    }
    response = client.put("/api/v1/profile/me", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test User Complete"
    assert data["phone"] == "+380123456789"
    assert data["description"] == "Test description"

def test_update_my_profile_validation_error(client, auth_headers):
    update_data = {"phone": "+380123456789"}
    response = client.put("/api/v1/profile/me", json=update_data, headers=auth_headers)
    assert response.status_code == 422

def test_update_my_profile_unauthorized(client):
    response = client.put("/api/v1/profile/me", json={"full_name": "Test User"})
    assert response.status_code == 401

def test_get_my_avatar_success(client, auth_headers):
    response = client.get("/api/v1/profile/avatar", headers=auth_headers)
    assert response.status_code in [200, 404]

def test_get_my_avatar_unauthorized(client):
    response = client.get("/api/v1/profile/avatar")
    assert response.status_code == 401

def test_upload_avatar_success(client, auth_headers, sample_image_file):
    response = client.post("/api/v1/profile/avatar", files=sample_image_file, headers=auth_headers)
    assert response.status_code == 200

def test_upload_avatar_validation_error(client, auth_headers):
    response = client.post("/api/v1/profile/avatar", files={}, headers=auth_headers)
    assert response.status_code == 422

def test_upload_avatar_unauthorized(client, sample_image_file):
    response = client.post("/api/v1/profile/avatar", files=sample_image_file)
    assert response.status_code == 401

def test_delete_avatar_success(client, auth_headers):
    response = client.delete("/api/v1/profile/avatar", headers=auth_headers)
    assert response.status_code == 200

def test_delete_avatar_unauthorized(client):
    response = client.delete("/api/v1/profile/avatar")
    assert response.status_code == 401

def test_get_user_public_profile_success(client, auth_headers):
    me_response = client.get("/api/v1/profile/me", headers=auth_headers)
    user_id = me_response.json()["id"]
    
    response = client.get(f"/api/v1/profile/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "role" in data

def test_get_user_public_profile_not_found(client):
    response = client.get("/api/v1/profile/nonexistent_id")
    assert response.status_code in [404, 422]

def test_get_user_avatar_success(client, auth_headers):
    me_response = client.get("/api/v1/profile/me", headers=auth_headers)
    user_id = me_response.json()["id"]
    
    response = client.get(f"/api/v1/profile/{user_id}/avatar")
    assert response.status_code in [200, 404]

def test_get_user_avatar_not_found(client):
    response = client.get("/api/v1/profile/nonexistent_id/avatar")
    assert response.status_code in [404, 422]
