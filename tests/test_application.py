import pytest
import asyncio
from datetime import datetime, timezone

def test_apply_for_event_success(client, vol2_headers, active_event_id):
    payload = {
        "motivation_letter": "I am ready to help",
        "agreed_to_share_contacts": True
    }
    response = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=vol2_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "Pending"

def test_apply_for_event_organizer_forbidden(client, org2_headers, active_event_id):
    payload = {"agreed_to_share_contacts": True}
    response = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=org2_headers)
    assert response.status_code in [403, 404]

def test_apply_for_event_validation_error(client, vol2_headers, active_event_id):
    payload = {"motivation_letter": "Missing agreement"}
    response = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=vol2_headers)
    assert response.status_code == 422

def test_get_event_applications_organizer_success(client, org1_headers, active_event_id, test_application_id):
    response = client.get(f"/api/v1/events/{active_event_id}/applications", headers=org1_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == active_event_id
    assert len(data["applications"]) >= 1

def test_get_event_applications_other_organizer_forbidden(client, org2_headers, active_event_id):
    response = client.get(f"/api/v1/events/{active_event_id}/applications", headers=org2_headers)
    assert response.status_code in [403, 404]

def test_get_event_applications_volunteer_forbidden(client, vol1_headers, active_event_id):
    response = client.get(f"/api/v1/events/{active_event_id}/applications", headers=vol1_headers)
    assert response.status_code in [403, 404]

def test_get_my_applications_volunteer_success(client, vol1_headers, test_application_id):
    response = client.get("/api/v1/applications/my", headers=vol1_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    ids = [app["id"] for app in data]
    assert test_application_id in ids

def test_get_my_applications_organizer_forbidden(client, org1_headers):
    response = client.get("/api/v1/applications/my", headers=org1_headers)
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert response.json() == []

def test_get_application_details_owner_success(client, vol1_headers, test_application_id):
    response = client.get(f"/api/v1/applications/{test_application_id}", headers=vol1_headers)
    assert response.status_code == 200
    assert response.json()["id"] == test_application_id

def test_get_application_details_organizer_success(client, org1_headers, test_application_id):
    response = client.get(f"/api/v1/applications/{test_application_id}", headers=org1_headers)
    assert response.status_code == 200

def test_get_application_details_other_volunteer_forbidden(client, vol2_headers, test_application_id):
    response = client.get(f"/api/v1/applications/{test_application_id}", headers=vol2_headers)
    assert response.status_code in [403, 404]

def test_get_application_details_other_organizer_forbidden(client, org2_headers, test_application_id):
    response = client.get(f"/api/v1/applications/{test_application_id}", headers=org2_headers)
    assert response.status_code in [403, 404]

def test_withdraw_application_owner_success(client, vol1_headers, active_event_id):
    payload = {"agreed_to_share_contacts": True}
    res = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=vol1_headers)
    app_id = res.json()["id"]

    response = client.patch(f"/api/v1/applications/{app_id}/withdraw", headers=vol1_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Withdrawn"

def test_withdraw_application_other_volunteer_forbidden(client, vol2_headers, test_application_id):
    response = client.patch(f"/api/v1/applications/{test_application_id}/withdraw", headers=vol2_headers)
    assert response.status_code in [403, 404]

def test_withdraw_application_organizer_forbidden(client, org1_headers, test_application_id):
    response = client.patch(f"/api/v1/applications/{test_application_id}/withdraw", headers=org1_headers)
    assert response.status_code in [403, 404]

def test_review_application_approve_success(client, org1_headers, active_event_id, vol2_headers):
    payload = {"agreed_to_share_contacts": True}
    res = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=vol2_headers)
    app_id = res.json()["id"]

    review_data = {"status": "Approved"}
    response = client.patch(f"/api/v1/applications/{app_id}/review", json=review_data, headers=org1_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Approved"

def test_review_application_reject_success(client, org1_headers, active_event_id, vol2_headers):
    payload = {"agreed_to_share_contacts": True}
    res = client.post(f"/api/v1/events/{active_event_id}/applications", json=payload, headers=vol2_headers)
    app_id = res.json()["id"]

    review_data = {"status": "Rejected", "rejection_reason": "Not a good fit"}
    response = client.patch(f"/api/v1/applications/{app_id}/review", json=review_data, headers=org1_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Rejected"

def test_review_application_other_organizer_forbidden(client, org2_headers, test_application_id):
    review_data = {"status": "Approved"}
    response = client.patch(f"/api/v1/applications/{test_application_id}/review", json=review_data, headers=org2_headers)
    assert response.status_code in [403, 404]

def test_review_application_volunteer_forbidden(client, vol1_headers, test_application_id):
    review_data = {"status": "Approved"}
    response = client.patch(f"/api/v1/applications/{test_application_id}/review", json=review_data, headers=vol1_headers)
    assert response.status_code in [403, 404]
