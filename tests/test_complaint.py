import pytest

def test_create_complaint_user_success(client, users_for_complaints):
    payload = {
        "target_type": "User",
        "target_id": users_for_complaints["org_id"],
        "violation_category": "Harassment",
        "description": "This user is sending inappropriate messages."
    }
    response = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["vol_headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["target_type"] == "User"
    assert data["accused_user_id"] == users_for_complaints["org_id"]
    assert data["status"] == "Pending"

def test_create_complaint_event_success(client, users_for_complaints, target_event):
    payload = {
        "target_type": "Event",
        "target_id": target_event,
        "violation_category": "Spam",
        "description": "This event seems to be a scam or spam."
    }
    response = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["vol_headers"])
    assert response.status_code == 201

def test_create_complaint_comment_success(client, users_for_complaints, target_comment):
    payload = {
        "target_type": "Comment",
        "target_id": target_comment,
        "violation_category": "Insults",
        "description": "The comment contains offensive language."
    }
    response = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["org_headers"])
    assert response.status_code == 201

def test_create_complaint_self_forbidden(client, users_for_complaints):
    payload = {
        "target_type": "User",
        "target_id": users_for_complaints["vol_id"],
        "violation_category": "Spam",
        "description": "Reporting myself just to test."
    }
    response = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["vol_headers"])
    assert response.status_code == 400

def test_create_complaint_invalid_target(client, users_for_complaints):
    payload = {
        "target_type": "Event",
        "target_id": "nonexistent_id",
        "violation_category": "Spam",
        "description": "This event seems to be a scam or spam."
    }
    response = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["vol_headers"])
    assert response.status_code == 404

def test_create_complaint_validation_error(client, users_for_complaints):
    payload = {
        "target_type": "User",
        "target_id": users_for_complaints["org_id"],
        "violation_category": "Sp", 
        "description": "Too short" 
    }
    response = client.post("/api/v1/complaints", json=payload, headers=users_for_complaints["vol_headers"])
    assert response.status_code == 422

def test_list_complaints_admin_success(client, admin_headers, sample_complaint):
    response = client.get("/api/v1/admin/complaints", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1

def test_list_complaints_admin_forbidden(client, users_for_complaints):
    response = client.get("/api/v1/admin/complaints", headers=users_for_complaints["vol_headers"])
    assert response.status_code == 403

def test_get_complaint_details_admin(client, admin_headers, sample_complaint):
    response = client.get(f"/api/v1/admin/complaints/{sample_complaint}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == sample_complaint

def test_reject_complaint_admin(client, admin_headers, sample_complaint):
    payload = {"admin_note": "No violation found after review."}
    response = client.patch(f"/api/v1/admin/complaints/{sample_complaint}/reject", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Rejected"
    assert data["admin_note"] == payload["admin_note"]

def test_delete_reported_content_event(client, admin_headers, sample_complaint):
    response = client.post(f"/api/v1/admin/complaints/{sample_complaint}/delete-content", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Resolved"
    assert "deleted by Administrator" in data["admin_note"]

def test_list_users_registry_admin(client, admin_headers):
    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_list_users_registry_forbidden(client, users_for_complaints):
    response = client.get("/api/v1/admin/users", headers=users_for_complaints["vol_headers"])
    assert response.status_code == 403

def test_block_user_success(client, admin_headers, users_for_complaints):
    payload = {"reason": "Violation of community guidelines."}
    response = client.patch(f"/api/v1/admin/users/{users_for_complaints['vol_id']}/block", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Blocked"
    assert data["block_reason"] == payload["reason"]

def test_block_already_blocked_user(client, admin_headers, users_for_complaints):
    payload = {"reason": "First block"}
    client.patch(f"/api/v1/admin/users/{users_for_complaints['vol_id']}/block", json=payload, headers=admin_headers)
    
    response = client.patch(f"/api/v1/admin/users/{users_for_complaints['vol_id']}/block", json=payload, headers=admin_headers)
    assert response.status_code == 400
    assert "already blocked" in response.json()["detail"]

def test_block_admin_forbidden(client, admin_headers):
    admin_id_res = client.get("/api/v1/profile/me", headers=admin_headers)
    admin_id = admin_id_res.json()["id"]

    payload = {"reason": "Trying to block an admin."}
    response = client.patch(f"/api/v1/admin/users/{admin_id}/block", json=payload, headers=admin_headers)
    assert response.status_code == 400

def test_unblock_user_success(client, admin_headers, users_for_complaints):
    payload = {"reason": "Block reason."}
    client.patch(f"/api/v1/admin/users/{users_for_complaints['vol_id']}/block", json=payload, headers=admin_headers)
    
    response = client.patch(f"/api/v1/admin/users/{users_for_complaints['vol_id']}/unblock", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Active"
    assert data["block_reason"] is None
