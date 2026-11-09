import pytest
from datetime import datetime, timezone
from bson import ObjectId
import asyncio

def test_list_my_notifications_all(client, notif_users, sample_notifications):
    response = client.get("/api/v1/notifications", headers=notif_users["user_headers"])
    assert response.status_code == 200
    data = response.json()
    
    assert data["unread_count"] == 1
    assert len(data["items"]) == 2  
    assert data["items"][0]["user_id"] == notif_users["user_id"]

def test_list_my_notifications_unread_only(client, notif_users, sample_notifications):
    response = client.get("/api/v1/notifications?unread_only=true", headers=notif_users["user_headers"])
    assert response.status_code == 200
    data = response.json()
    
    assert data["unread_count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["is_read"] is False

def test_list_notifications_unauthorized(client):
    response = client.get("/api/v1/notifications")
    assert response.status_code == 401

def test_mark_single_notification_as_read_success(client, notif_users, sample_notifications):
    notif_id = sample_notifications["unread_id"]
    response = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=notif_users["user_headers"])
    
    assert response.status_code == 200
    assert response.json()["id"] == notif_id
    assert response.json()["is_read"] is True

def test_mark_single_notification_other_user_forbidden(client, notif_users, sample_notifications, mock_db):
    notif_id = sample_notifications["unread_id"]
    
    response = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=notif_users["other_headers"])
    
    db_notif = asyncio.run(mock_db["notifications"].find_one({"_id": ObjectId(notif_id)}))
    
    assert db_notif["is_read"] is False

def test_mark_single_notification_not_found(client, notif_users):
    response = client.patch("/api/v1/notifications/nonexistent_id/read", headers=notif_users["user_headers"])
    assert response.status_code in [404, 422]

def test_mark_all_notifications_as_read(client, notif_users, sample_notifications):
    list_res1 = client.get("/api/v1/notifications", headers=notif_users["user_headers"])
    assert list_res1.json()["unread_count"] > 0
    
    response = client.patch("/api/v1/notifications/read-all", headers=notif_users["user_headers"])
    assert response.status_code == 200
    assert "updated_count" in response.json()
    assert response.json()["updated_count"] >= 1
    
    list_res2 = client.get("/api/v1/notifications", headers=notif_users["user_headers"])
    assert list_res2.json()["unread_count"] == 0
