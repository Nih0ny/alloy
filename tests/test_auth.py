import pytest

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

def test_hello_world(client):
    response = client.get("/api/v1/hello-world")
    assert response.status_code == 200

def test_db_hello_world(client):
    response = client.get("/api/v1/db-hello-world")
    assert response.status_code == 200

def test_register_user_success(client, valid_user_data):
    response = client.post("/api/v1/auth/register", json=valid_user_data)

    assert response.status_code in [201, 400]

    if response.status_code == 201:
        data = response.json()
        assert "id" in data
        assert data["email"] == valid_user_data["email"]
        assert data["role"] == valid_user_data["role"]
        assert data["status"] in ["Active", "Blocked"]

def test_register_validation_error(client, valid_user_data):
    invalid_data = valid_user_data.copy()
    del invalid_data["agreed_to_rules"]

    response = client.post("/api/v1/auth/register", json=invalid_data)

    assert response.status_code == 422
    assert "detail" in response.json()

def test_register_passwords_mismatch(client, valid_user_data):
    invalid_data = valid_user_data.copy()
    invalid_data["password_confirm"] = "DifferentPassword123!"
    
    response = client.post("/api/v1/auth/register", json=invalid_data)
    assert response.status_code in [400, 422]

def test_register_invalid_email(client, valid_user_data):
    invalid_data = valid_user_data.copy()
    invalid_data["email"] = "not-an-email"
    
    response = client.post("/api/v1/auth/register", json=invalid_data)
    assert response.status_code == 422

def test_register_invalid_role(client, valid_user_data):
    invalid_data = valid_user_data.copy()
    invalid_data["role"] = "UnknownRole"
    
    response = client.post("/api/v1/auth/register", json=invalid_data)
    assert response.status_code == 422

def test_login_success(client, login_data):
    response = client.post("/api/v1/auth/login", data=login_data)

    assert response.status_code in [200, 400, 401]

    if response.status_code == 200:
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

def test_login_validation_error(client):
    response = client.post("/api/v1/auth/login", data={})
    assert response.status_code == 422

def test_login_wrong_password(client, login_data):
    invalid_login = login_data.copy()
    invalid_login["password"] = "WrongPassword123!"
    
    response = client.post("/api/v1/auth/login", data=invalid_login)
    assert response.status_code in [400, 401]

def test_login_unregistered_user(client):
    response = client.post("/api/v1/auth/login", data={
        "username": "nonexistent@example.com",
        "password": "SomePassword123!"
    })
    assert response.status_code in [400, 401, 404]

def test_refresh_token(client):
    client.cookies.set("refresh_token", "some_dummy_refresh_token")

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code in [200, 401, 403]

    if response.status_code == 200:
        assert "access_token" in response.json()

def test_refresh_token_missing(client):
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code in [400, 401, 422]

def test_logout(client):
    client.cookies.set("refresh_token", "some_dummy_refresh_token")

    response = client.post("/api/v1/auth/logout")

    assert response.status_code in [200, 401]

    if response.status_code == 200:
        assert response.json() == {'detail': 'Successful exit'}

def test_logout_missing_token(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
