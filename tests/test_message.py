def test_send_message_success(client, comm_users):
    payload = {"recipient_id": comm_users["vol2_id"], "text": "Hello Vol2!"}
    res = client.post("/api/v1/messages", json=payload, headers=comm_users["vol1"])
    assert res.status_code == 201
    assert res.json()["text"] == "Hello Vol2!"

def test_send_message_to_self(client, comm_users):
    payload = {"recipient_id": comm_users["vol1_id"], "text": "Self note"}
    res = client.post("/api/v1/messages", json=payload, headers=comm_users["vol1"])
    assert res.status_code == 400

def test_send_message_to_non_existent(client, comm_users):
    payload = {"recipient_id": "invalid_id", "text": "Hello"}
    res = client.post("/api/v1/messages", json=payload, headers=comm_users["vol1"])
    assert res.status_code in [404, 422]

def test_send_message_to_blocked(client, comm_users):
    payload = {"recipient_id": comm_users["blocked_id"], "text": "Are you there?"}
    res = client.post("/api/v1/messages", json=payload, headers=comm_users["vol1"])
    assert res.status_code == 400

def test_send_message_with_invalid_event(client, comm_users):
    payload = {"recipient_id": comm_users["vol2_id"], "text": "Look at this", "event_id": "invalid_event"}
    res = client.post("/api/v1/messages", json=payload, headers=comm_users["vol1"])
    assert res.status_code in [404, 422]

def test_get_conversations_and_unread_count(client, comm_users):
    client.post("/api/v1/messages", json={"recipient_id": comm_users["vol2_id"], "text": "Msg 1"}, headers=comm_users["vol1"])
    client.post("/api/v1/messages", json={"recipient_id": comm_users["vol2_id"], "text": "Msg 2"}, headers=comm_users["vol1"])
    
    res = client.get("/api/v1/messages/conversations", headers=comm_users["vol2"])
    assert res.status_code == 200
    convs = res.json()
    assert len(convs) >= 1
    vol1_conv = next(c for c in convs if c["interlocutor_id"] == comm_users["vol1_id"])
    assert vol1_conv["unread_count"] >= 2
    assert vol1_conv["last_message_text"] == "Msg 2"

def test_get_conversation_history_marks_read(client, comm_users):
    client.post("/api/v1/messages", json={"recipient_id": comm_users["vol2_id"], "text": "Hello"}, headers=comm_users["vol1"])
    
    res_hist = client.get(f"/api/v1/messages/conversations/{comm_users['vol1_id']}", headers=comm_users["vol2"])
    assert res_hist.status_code == 200
    assert isinstance(res_hist.json(), list)

    res_convs = client.get("/api/v1/messages/conversations", headers=comm_users["vol2"])
    vol1_conv = next(c for c in res_convs.json() if c["interlocutor_id"] == comm_users["vol1_id"])
    assert vol1_conv["unread_count"] == 0

def test_get_conversation_invalid_interlocutor(client, comm_users):
    res = client.get("/api/v1/messages/conversations/invalid_user", headers=comm_users["vol1"])
    assert res.status_code in [404, 422]
