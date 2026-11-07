def test_support_create_guest_with_email(client):
    payload = {"subject": "Need help", "message": "I forgot my password and cannot reset it.", "contact_email": "guest@test.com"}
    res = client.post("/api/v1/support", json=payload)
    assert res.status_code == 201
    assert res.json()["status"] == "New"
    assert res.json()["contact_email"] == "guest@test.com"

def test_support_create_guest_no_email(client):
    payload = {"subject": "Need help", "message": "I forgot my password and cannot reset it."}
    res = client.post("/api/v1/support", json=payload)
    assert res.status_code in [400, 422]

def test_support_create_auth_user(client, comm_users):
    payload = {"subject": "Bug report", "message": "The system crashed when I clicked the button."}
    res = client.post("/api/v1/support", json=payload, headers=comm_users["vol1"])
    assert res.status_code == 201
    assert res.json()["user_id"] == comm_users["vol1_id"]

def test_support_create_validation_error(client):
    payload = {"subject": "Hi", "message": "Short", "contact_email": "guest@test.com"}
    res = client.post("/api/v1/support", json=payload)
    assert res.status_code == 422

def test_support_get_my_tickets(client, comm_users):
    res_create = client.post("/api/v1/support", json={"subject": "Ticket 1", "message": "Detail 1234567890"}, headers=comm_users["vol1"])
    assert res_create.status_code == 201
    
    res = client.get("/api/v1/support/my", headers=comm_users["vol1"])
    assert res.status_code == 200
    assert len(res.json()) >= 1

def test_support_admin_list_tickets(client, comm_admin_headers, comm_users):
    client.post("/api/v1/support", json={"subject": "Ticket 2", "message": "Detail 1234567890"}, headers=comm_users["vol2"])
    res = client.get("/api/v1/support/admin", headers=comm_admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_support_admin_filter_tickets(client, comm_admin_headers):
    res = client.get("/api/v1/support/admin?status_filter=Resolved", headers=comm_admin_headers)
    assert res.status_code == 200
    assert all(t["status"] == "Resolved" for t in res.json())

def test_support_list_tickets_forbidden(client, comm_users):
    res = client.get("/api/v1/support/admin", headers=comm_users["vol1"])
    assert res.status_code == 403

def test_support_admin_update_ticket(client, comm_admin_headers, comm_users):
    t_res = client.post("/api/v1/support", json={"subject": "Ticket 3", "message": "Detail 1234567890"}, headers=comm_users["vol1"])
    assert t_res.status_code == 201
    t_id = t_res.json()["id"]

    res = client.patch(f"/api/v1/support/admin/{t_id}", json={"status": "In Progress", "admin_reply": "Working on it"}, headers=comm_admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "In Progress"
    assert res.json()["admin_reply"] == "Working on it"

def test_support_update_ticket_forbidden(client, comm_users):
    res = client.patch("/api/v1/support/admin/some_id", json={"status": "Resolved"}, headers=comm_users["vol1"])
    assert res.status_code == 403
