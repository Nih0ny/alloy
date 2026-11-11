import pytest

def test_unverified_cannot_create_event(client, unverified_org_headers):
    payload = {
        "title": "Test Event",
        "description": "Very long description to pass the minimum fifty characters limit in validations.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {"address": "Valid Address", "latitude": 49.0, "longitude": 26.0},
        "volunteer_quota": 5
    }
    res = client.post("/api/v1/events", json=payload, headers=unverified_org_headers)
    assert res.status_code == 403
    assert "email" in res.json()["detail"].lower() or "verif" in res.json()["detail"].lower()

def test_unverified_cannot_apply(client, unverified_user_headers, active_event_id):
    payload = {
        "motivation_letter": "Let me in!",
        "agreed_to_share_contacts": True
    }
    res = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=unverified_user_headers)
    assert res.status_code == 403
    assert "email" in res.json()["detail"].lower() or "verif" in res.json()["detail"].lower()

def test_unverified_cannot_comment(client, unverified_user_headers, active_event_id):
    payload = {"text": "What time does it start?"}
    res = client.post(f"/api/v1/events/{active_event_id}/comments", json=payload, headers=unverified_user_headers)
    assert res.status_code == 403

def test_unverified_cannot_send_message(client, unverified_user_headers, comm_users):
    payload = {
        "recipient_id": comm_users["org_id"], 
        "text": "Hello there"
    }
    res = client.post("/api/v1/messages", json=payload, headers=unverified_user_headers)
    assert res.status_code == 403

def test_unverified_cannot_submit_complaint(client, unverified_user_headers, comm_users):
    payload = {
        "target_type": "User",
        "target_id": comm_users["org_id"],
        "violation_category": "Spam",
        "description": "Some description about the issue."
    }
    res = client.post("/api/v1/complaints", json=payload, headers=unverified_user_headers)
    assert res.status_code == 403

def test_unverified_auth_user_support_ticket(client, unverified_user_headers):
    payload = {
        "subject": "Help me", 
        "message": "I cannot verify my email, the link is broken."
    }
    res = client.post("/api/v1/support", json=payload, headers=unverified_user_headers)
    
    assert res.status_code in [200, 201]
