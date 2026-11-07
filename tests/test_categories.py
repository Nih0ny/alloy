import pytest

def test_list_public_categories(client):
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_list_categories_for_admin_success(client, admin_headers):
    response = client.get("/api/v1/categories/admin", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "active_events_count" in data[0]
        assert "is_archived" in data[0]

def test_list_categories_for_admin_forbidden(client, org_headers):
    response = client.get("/api/v1/categories/admin", headers=org_headers)
    assert response.status_code == 403

def test_create_category_admin_success(client, admin_headers):
    payload = {"name": "Ecology"}
    response = client.post("/api/v1/categories", json=payload, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Ecology"

def test_create_category_validation_error(client, admin_headers):
    payload = {"name": " "}
    response = client.post("/api/v1/categories", json=payload, headers=admin_headers)
    assert response.status_code == 422

def test_create_category_forbidden(client, org_headers):
    payload = {"name": "Animals"}
    response = client.post("/api/v1/categories", json=payload, headers=org_headers)
    assert response.status_code == 403

def test_create_category_duplicate(client, admin_headers):
    payload = {"name": "DuplicateCategory"}
    client.post("/api/v1/categories", json=payload, headers=admin_headers)
    
    response2 = client.post("/api/v1/categories", json=payload, headers=admin_headers)
    assert response2.status_code == 409

def test_update_category_admin_success(client, admin_headers):
    res_create = client.post("/api/v1/categories", json={"name": "Old Name"}, headers=admin_headers)
    cat_id = res_create.json()["id"]
    
    res_update = client.put(f"/api/v1/categories/{cat_id}", json={"name": "New Name"}, headers=admin_headers)
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "New Name"

def test_update_category_duplicate(client, admin_headers):
    client.post("/api/v1/categories", json={"name": "Target1"}, headers=admin_headers)
    res2 = client.post("/api/v1/categories", json={"name": "Target2"}, headers=admin_headers)
    cat2_id = res2.json()["id"]

    res_update = client.put(f"/api/v1/categories/{cat2_id}", json={"name": "Target1"}, headers=admin_headers)
    assert res_update.status_code == 409

def test_update_category_not_found(client, admin_headers):
    res = client.put("/api/v1/categories/60c72b2f9b1d8b5a5f8e1234", json={"name": "New"}, headers=admin_headers)
    assert res.status_code == 404

def test_delete_category_no_events_success(client, admin_headers):
    res_create = client.post("/api/v1/categories", json={"name": "To Delete Permanently"}, headers=admin_headers)
    cat_id = res_create.json()["id"]

    res_delete = client.delete(f"/api/v1/categories/{cat_id}", headers=admin_headers)
    assert res_delete.status_code == 200
    assert res_delete.json()["action"] == "deleted"

def test_delete_category_with_events_archives(client, admin_headers, org_headers):
    res_create = client.post("/api/v1/categories", json={"name": "To Archive"}, headers=admin_headers)
    cat_id = res_create.json()["id"]

    event_payload = {
        "title": "Event tied to category",
        "description": "Category test description minimum 50 characters required here.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {"address": "Test Address", "latitude": 49.0, "longitude": 26.0},
        "volunteer_quota": 5,
        "category_id": cat_id
    }
    client.post("/api/v1/events", json=event_payload, headers=org_headers)

    res_delete = client.delete(f"/api/v1/categories/{cat_id}", headers=admin_headers)
    assert res_delete.status_code == 200
    assert res_delete.json()["action"] == "archived"

    pub_categories = client.get("/api/v1/categories").json()
    assert cat_id not in [c["id"] for c in pub_categories]

def test_restore_archived_category(client, admin_headers, org_headers):
    res_create = client.post("/api/v1/categories", json={"name": "Restore Me"}, headers=admin_headers)
    cat_id = res_create.json()["id"]

    event_payload = {
        "title": "Event tied to category 2",
        "description": "Category test description minimum 50 characters required here.",
        "event_date": "2026-12-01T10:00:00Z",
        "location": {"address": "Test Address", "latitude": 49.0, "longitude": 26.0},
        "volunteer_quota": 5,
        "category_id": cat_id
    }
    client.post("/api/v1/events", json=event_payload, headers=org_headers)
    client.delete(f"/api/v1/categories/{cat_id}", headers=admin_headers)

    res_restore = client.post("/api/v1/categories", json={"name": "Restore Me"}, headers=admin_headers)
    assert res_restore.status_code == 201
    assert res_restore.json()["id"] == cat_id
    assert res_restore.json()["is_archived"] is False
