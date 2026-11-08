import pytest
import respx
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock
from httpx import Response as HttpxResponse

from alloy.core import security
from alloy.services.auth_service import AuthService

def mock_google_userinfo_success(route):
    route.mock(return_value=HttpxResponse(200, json={
        "email": "google_user@example.com",
        "name": "Google Test User",
        "picture": "https://example.com/google_avatar.jpg"
    }))

def mock_facebook_userinfo_success(route):
    route.mock(return_value=HttpxResponse(200, json={
        "email": "facebook_user@example.com",
        "name": "Facebook Test User",
        "picture": {"data": {"url": "https://example.com/fb_avatar.jpg"}}
    }))

def mock_google_userinfo_no_email(route):
    route.mock(return_value=HttpxResponse(200, json={
        "name": "No Email User"
    }))

def mock_oauth_unauthorized(route):
    route.mock(return_value=HttpxResponse(401, json={"error": "invalid_token"}))

@patch.object(AuthService, "_fetch_google_user_info", new_callable=AsyncMock)
def test_oauth_login_google_new_user_success(mock_fetch, client):
    mock_fetch.return_value = {
        "email": "google_user@example.com",
        "full_name": "Google Test User",
        "avatar_url": "https://example.com/google_avatar.jpg"
    }
    
    payload = {
        "token": "fake_google_token",
        "role": "Volunteer",
        "agreed_to_rules": True
    }
    
    response = client.post("/api/v1/auth/oauth/google", json=payload)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.cookies


@patch.object(AuthService, "_fetch_facebook_user_info", new_callable=AsyncMock)
def test_oauth_login_facebook_new_user_success(mock_fetch, client):
    mock_fetch.return_value = {
        "email": "facebook_user@example.com",
        "full_name": "Facebook Test User",
        "avatar_url": "https://example.com/fb_avatar.jpg"
    }
    
    payload = {
        "token": "fake_fb_token",
        "role": "Organizer",
        "agreed_to_rules": True
    }
    
    response = client.post("/api/v1/auth/oauth/facebook", json=payload)
    assert response.status_code == 200
    assert "access_token" in response.json()


@patch.object(AuthService, "_fetch_google_user_info", new_callable=AsyncMock)
def test_oauth_login_invalid_token(mock_fetch, client):
    mock_fetch.side_effect = HTTPException(
        status_code=401, 
        detail="Failed to authenticate Google account (invalid token)"
    )
    
    payload = {
        "token": "invalid_google_token",
        "role": "Volunteer",
        "agreed_to_rules": True
    }
    
    response = client.post("/api/v1/auth/oauth/google", json=payload)
    assert response.status_code == 401
    assert "invalid token" in response.json()["detail"].lower()


@patch.object(AuthService, "_fetch_google_user_info", new_callable=AsyncMock)
def test_oauth_login_no_email_provided(mock_fetch, client):
    mock_fetch.return_value = {
        "email": None,
        "full_name": "No Email User",
        "avatar_url": None
    }
    
    payload = {
        "token": "fake_token_without_email",
        "role": "Volunteer",
        "agreed_to_rules": True
    }
    
    response = client.post("/api/v1/auth/oauth/google", json=payload)
    assert response.status_code == 400
    assert "did not provide access to your email" in response.json()["detail"].lower()


def test_oauth_validation_admin_role_forbidden(client):
    payload = {
        "token": "some_token",
        "role": "Admin",
        "agreed_to_rules": True
    }
    response = client.post("/api/v1/auth/oauth/google", json=payload)
    assert response.status_code == 422
    assert "Administrator" in response.text


def test_oauth_validation_disagreed_to_rules(client):
    payload = {
        "token": "some_token",
        "role": "Volunteer",
        "agreed_to_rules": False
    }
    response = client.post("/api/v1/auth/oauth/google", json=payload)
    assert response.status_code == 422

def test_forgot_password_success(client, valid_user_data):
    client.post("/api/v1/auth/register", json=valid_user_data)
    
    payload = {"email": valid_user_data["email"]}
    response = client.post("/api/v1/auth/forgot-password", json=payload)
    
    assert response.status_code == 200
    assert "instructions have been sent" in response.json()["detail"]

def test_forgot_password_unregistered_email(client):
    payload = {"email": "never_registered@example.com"}
    response = client.post("/api/v1/auth/forgot-password", json=payload)
    
    assert response.status_code == 200
    assert "instructions have been sent" in response.json()["detail"]

def test_forgot_password_invalid_email(client):
    payload = {"email": "invalid_email_format"}
    response = client.post("/api/v1/auth/forgot-password", json=payload)
    assert response.status_code == 422

def test_reset_password_success(client, valid_user_data):
    client.post("/api/v1/auth/register", json=valid_user_data)
    
    reset_token = security.create_password_reset_token(valid_user_data["email"])
    
    with patch("alloy.services.auth_service.security.create_password_reset_token", return_value=reset_token):
        client.post("/api/v1/auth/forgot-password", json={"email": valid_user_data["email"]})
        
        payload = {
            "reset_token": reset_token,
            "new_password": "NewStrongPassword123!",
            "new_password_confirm": "NewStrongPassword123!"
        }
        
        response = client.post("/api/v1/auth/reset-password", json=payload)
        assert response.status_code == 200
        assert "successfully updated" in response.json()["detail"]
        
        login_data = {"username": valid_user_data["email"], "password": "NewStrongPassword123!"}
        login_res = client.post("/api/v1/auth/login", data=login_data)
        assert login_res.status_code == 200

def test_reset_password_invalid_token(client):
    payload = {
        "reset_token": "invalid_or_fake_token",
        "new_password": "NewStrongPassword123!",
        "new_password_confirm": "NewStrongPassword123!"
    }
    response = client.post("/api/v1/auth/reset-password", json=payload)
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()

def test_reset_password_passwords_mismatch(client):
    payload = {
        "reset_token": "some_token",
        "new_password": "NewStrongPassword123!",
        "new_password_confirm": "DifferentPassword123!"
    }
    response = client.post("/api/v1/auth/reset-password", json=payload)
    assert response.status_code == 422

def test_reset_password_too_short(client):
    payload = {
        "reset_token": "some_token",
        "new_password": "short",
        "new_password_confirm": "short"
    }
    response = client.post("/api/v1/auth/reset-password", json=payload)
    assert response.status_code == 422
