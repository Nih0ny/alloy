import pytest

@pytest.fixture
def created_event_id(client, organizer_headers, event_create_data):
    res = client.post("/api/v1/events", json=event_create_data, headers=organizer_headers)
    return res.json()["id"]


def test_list_public_events_success(client):
    response = client.get("/api/v1/events")
    assert response.status_code == 200


def test_create_event_organizer(client, organizer_headers, event_create_data):
    response = client.post("/api/v1/events", json=event_create_data, headers=organizer_headers)
    assert response.status_code == 201
    assert response.json()["title"] == event_create_data["title"]


def test_create_event_volunteer_forbidden(client, volunteer_headers, event_create_data):
    response = client.post("/api/v1/events", json=event_create_data, headers=volunteer_headers)
    assert response.status_code == 403


def test_get_my_events_organizer(client, organizer_headers, created_event_id):
    response = client.get("/api/v1/events/my", headers=organizer_headers)
    assert response.status_code == 200
    ids = [ev["id"] for ev in response.json()]
    assert created_event_id in ids


def test_get_pending_moderation_admin(client, admin_headers, created_event_id):
    response = client.get("/api/v1/events/moderation/pending", headers=admin_headers)
    assert response.status_code == 200
    ids = [ev["id"] for ev in response.json()]
    assert created_event_id in ids


def test_get_pending_moderation_organizer_forbidden(client, organizer_headers):
    response = client.get("/api/v1/events/moderation/pending", headers=organizer_headers)
    assert response.status_code == 403


def test_update_event_creator(client, organizer_headers, created_event_id):
    update_data = {"title": "Updated Event Title Minimum Length"}
    response = client.put(f"/api/v1/events/{created_event_id}", json=update_data, headers=organizer_headers)
    assert response.status_code == 200


def test_update_event_other_organizer_forbidden(client, another_organizer_headers, created_event_id):
    update_data = {"title": "Malicious Update Attempt Title"}
    response = client.put(f"/api/v1/events/{created_event_id}", json=update_data, headers=another_organizer_headers)
    assert response.status_code in [403, 404]


def test_change_event_status_creator_before_approval(client, organizer_headers, created_event_id):
    status_data = {"status": "In Process"}
    response = client.patch(f"/api/v1/events/{created_event_id}/status", json=status_data, headers=organizer_headers)
    
    assert response.status_code == 400
    assert "Administrator moderation" in response.json()["detail"]

def test_change_event_status_creator_after_approval(client, admin_headers, organizer_headers, created_event_id):
    mod_data = {"action": "Approved"}
    client.patch(f"/api/v1/events/{created_event_id}/moderation", json=mod_data, headers=admin_headers)

    status_data = {"status": "In Process"}
    response = client.patch(f"/api/v1/events/{created_event_id}/status", json=status_data, headers=organizer_headers)
    
    assert response.status_code == 200
    assert response.json()["status"] == "In Process"


def test_change_event_status_other_organizer_forbidden(client, another_organizer_headers, created_event_id):
    status_data = {"status": "In Process"}
    response = client.patch(f"/api/v1/events/{created_event_id}/status", json=status_data, headers=another_organizer_headers)
    assert response.status_code in [403, 404]


def test_moderate_event_admin_approve(client, admin_headers, created_event_id):
    mod_data = {"action": "Approved"}
    response = client.patch(f"/api/v1/events/{created_event_id}/moderation", json=mod_data, headers=admin_headers)
    assert response.status_code == 200


def test_moderate_event_organizer_forbidden(client, organizer_headers, created_event_id):
    mod_data = {"action": "Approved"}
    response = client.patch(f"/api/v1/events/{created_event_id}/moderation", json=mod_data, headers=organizer_headers)
    assert response.status_code == 403


def test_moderate_event_reject_and_visibility(client, admin_headers, organizer_headers, volunteer_headers, created_event_id):
    mod_data = {"action": "Rejected", "rejection_reason": "Inappropriate content"}
    client.patch(f"/api/v1/events/{created_event_id}/moderation", json=mod_data, headers=admin_headers)
    
    res_creator = client.get(f"/api/v1/events/{created_event_id}", headers=organizer_headers)
    assert res_creator.status_code == 200
    assert res_creator.json()["moderation_status"] == "Rejected"
    
    res_volunteer = client.get(f"/api/v1/events/{created_event_id}", headers=volunteer_headers)
    assert res_volunteer.status_code in [403, 404]
    
    res_public = client.get(f"/api/v1/events/{created_event_id}")
    assert res_public.status_code in [401, 403, 404]

    res_public_list = client.get("/api/v1/events")
    public_ids = [ev["id"] for ev in res_public_list.json()]
    assert created_event_id not in public_ids


def test_upload_event_photos_creator(client, organizer_headers, created_event_id):
    files = [("files", ("photo.jpg", b"fake", "image/jpeg"))]
    response = client.post(f"/api/v1/events/{created_event_id}/photos", files=files, headers=organizer_headers)
    assert response.status_code == 200


def test_upload_event_photos_other_organizer_forbidden(client, another_organizer_headers, created_event_id):
    files = [("files", ("photo.jpg", b"fake", "image/jpeg"))]
    response = client.post(f"/api/v1/events/{created_event_id}/photos", files=files, headers=another_organizer_headers)
    assert response.status_code in [403, 404]


def test_delete_event_other_organizer_forbidden(client, another_organizer_headers, created_event_id):
    response = client.delete(f"/api/v1/events/{created_event_id}", headers=another_organizer_headers)
    assert response.status_code in [403, 404]


def test_delete_event_creator(client, organizer_headers, created_event_id):
    response = client.delete(f"/api/v1/events/{created_event_id}", headers=organizer_headers)
    assert response.status_code == 204
    
    verify_response = client.get(f"/api/v1/events/{created_event_id}", headers=organizer_headers)
    assert verify_response.status_code == 404


