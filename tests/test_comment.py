def test_add_comment_success(client, comm_users, comm_events):
    payload = {"text": "Is there parking nearby?"}
    res = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json=payload, headers=comm_users["vol1"])
    assert res.status_code == 201
    assert res.json()["author_id"] == comm_users["vol1_id"]

def test_add_comment_invalid_event(client, comm_users):
    payload = {"text": "Test"}
    res = client.post("/api/v1/events/invalid_id/comments", json=payload, headers=comm_users["vol1"])
    assert res.status_code in [404, 422]

def test_add_comment_closed_event(client, comm_users, comm_events):
    payload = {"text": "Test on closed"}
    res = client.post(f"/api/v1/events/{comm_events['closed_id']}/comments", json=payload, headers=comm_users["vol1"])
    assert res.status_code == 400

def test_reply_to_comment_success(client, comm_users, comm_events):
    payload1 = {"text": "First comment"}
    c1 = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json=payload1, headers=comm_users["vol1"])
    c1_id = c1.json()["id"]

    payload2 = {"text": "Replying to first", "reply_to_comment_id": c1_id}
    c2 = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json=payload2, headers=comm_users["org"])
    assert c2.status_code == 201
    assert c2.json()["reply_to_comment_id"] == c1_id

def test_reply_to_non_existent_comment(client, comm_users, comm_events):
    payload = {"text": "Reply", "reply_to_comment_id": "invalid_comment_id"}
    res = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json=payload, headers=comm_users["vol1"])
    assert res.status_code in [404, 422]

def test_list_event_comments(client, comm_events):
    res = client.get(f"/api/v1/events/{comm_events['open_id']}/comments")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_list_comments_invalid_event(client):
    res = client.get("/api/v1/events/invalid_id/comments")
    assert res.status_code in [404, 422]

def test_delete_comment_by_author(client, comm_users, comm_events):
    c1 = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json={"text": "To delete"}, headers=comm_users["vol1"])
    c_id = c1.json()["id"]
    res = client.delete(f"/api/v1/comments/{c_id}", headers=comm_users["vol1"])
    assert res.status_code == 204

def test_delete_comment_by_organizer(client, comm_users, comm_events):
    c1 = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json={"text": "To delete org"}, headers=comm_users["vol2"])
    c_id = c1.json()["id"]
    res = client.delete(f"/api/v1/comments/{c_id}", headers=comm_users["org"])
    assert res.status_code == 204

def test_delete_comment_by_admin(client, comm_users, comm_events, comm_admin_headers):
    c1 = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json={"text": "To delete admin"}, headers=comm_users["vol2"])
    c_id = c1.json()["id"]
    res = client.delete(f"/api/v1/comments/{c_id}", headers=comm_admin_headers)
    assert res.status_code == 204

def test_delete_comment_forbidden(client, comm_users, comm_events):
    c1 = client.post(f"/api/v1/events/{comm_events['open_id']}/comments", json={"text": "To delete forbidden"}, headers=comm_users["org"])
    c_id = c1.json()["id"]
    res = client.delete(f"/api/v1/comments/{c_id}", headers=comm_users["vol1"])
    assert res.status_code == 403

def test_delete_non_existent_comment(client, comm_users):
    res = client.delete("/api/v1/comments/invalid_id", headers=comm_users["vol1"])
    assert res.status_code in [404, 422]
