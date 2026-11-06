import pytest

def test_get_review_form_info_organizer_checks_volunteer(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/form-info/{review_context['vol_id']}"
    response = client.get(url, headers=review_context["org_headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["reviewee_id"] == review_context["vol_id"]
    assert "can_review" in data
    assert "already_reviewed" in data

def test_get_review_form_info_volunteer_checks_organizer(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/form-info/{review_context['org_id']}"
    response = client.get(url, headers=review_context["vol_headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["reviewee_id"] == review_context["org_id"]
    assert "can_review" in data

def test_get_review_form_info_unauthorized(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/form-info/{review_context['vol_id']}"
    response = client.get(url)
    assert response.status_code == 401

def test_review_volunteer_success(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/volunteer"
    payload = {
        "rating": 5,
        "comment": "Great volunteer, highly recommended!",
        "volunteer_id": review_context["vol_id"]
    }
    response = client.post(url, json=payload, headers=review_context["org_headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["rating"] == 5
    assert data["reviewee_id"] == review_context["vol_id"]
    assert data["reviewer_id"] == review_context["org_id"]

def test_review_volunteer_validation_error(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/volunteer"
    payload = {
        "rating": 6,
        "comment": "1",
        "volunteer_id": review_context["vol_id"]
    }
    response = client.post(url, json=payload, headers=review_context["org_headers"])
    assert response.status_code == 422

def test_review_volunteer_wrong_role(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/volunteer"
    payload = {
        "rating": 5,
        "comment": "Great volunteer",
        "volunteer_id": review_context["vol_id"]
    }
    response = client.post(url, json=payload, headers=review_context["vol_headers"])
    assert response.status_code in [400, 403]

def test_review_organizer_success(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/organizer"
    payload = {
        "rating": 4,
        "comment": "Good organization, but some delays."
    }
    response = client.post(url, json=payload, headers=review_context["vol_headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["rating"] == 4
    assert data["reviewee_id"] == review_context["org_id"]
    assert data["reviewer_id"] == review_context["vol_id"]

def test_review_organizer_validation_error(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/organizer"
    payload = {
        "rating": 0,
        "comment": "Bad"
    }
    response = client.post(url, json=payload, headers=review_context["vol_headers"])
    assert response.status_code == 422

def test_review_organizer_wrong_role(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/organizer"
    payload = {
        "rating": 4,
        "comment": "Reviewing myself?"
    }
    response = client.post(url, json=payload, headers=review_context["org_headers"])
    assert response.status_code in [400, 403]

def test_duplicate_review_volunteer(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/volunteer"
    payload = {
        "rating": 5,
        "comment": "First review",
        "volunteer_id": review_context["vol_id"]
    }
    client.post(url, json=payload, headers=review_context["org_headers"])
    
    response2 = client.post(url, json=payload, headers=review_context["org_headers"])
    assert response2.status_code == 409

def test_duplicate_review_organizer(client, review_context):
    url = f"/api/v1/events/{review_context['event_id']}/reviews/organizer"
    payload = {
        "rating": 5,
        "comment": "First review"
    }
    client.post(url, json=payload, headers=review_context["vol_headers"])
    
    response2 = client.post(url, json=payload, headers=review_context["vol_headers"])
    assert response2.status_code == 409

def test_list_event_reviews_success(client, review_context):
    vol_url = f"/api/v1/events/{review_context['event_id']}/reviews/volunteer"
    client.post(vol_url, json={"rating": 5, "comment": "Good vol", "volunteer_id": review_context["vol_id"]}, headers=review_context["org_headers"])
    
    org_url = f"/api/v1/events/{review_context['event_id']}/reviews/organizer"
    client.post(org_url, json={"rating": 4, "comment": "Good org"}, headers=review_context["vol_headers"])
    
    list_url = f"/api/v1/events/{review_context['event_id']}/reviews"
    response = client.get(list_url)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

def test_list_event_reviews_invalid_event(client):
    response = client.get("/api/v1/events/invalid_event_id/reviews")
    assert response.status_code in [404, 422, 200]
    if response.status_code == 200:
        assert response.json() == []
