"""Тести видалення акаунту (DELETE /users/me)."""
import json


def _delete_json(client, headers, payload):
    return client.request(
        "DELETE",
        "/users/me",
        content=json.dumps(payload),
        headers={**headers, "Content-Type": "application/json"},
    )


def create_trip(client, headers, title="Похід"):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def join_by_invite(client, org, guest, trip_id):
    token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=guest)
    assert r.status_code == 200, r.text


def add_item(client, headers, trip_id, name, assign_headers=None):
    cat = client.post(
        f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=headers
    )
    assert cat.status_code == 200, cat.text
    item = client.post(
        "/items/",
        json={"name": name, "quantity": 1, "trip_id": trip_id, "category_id": cat.json()["id"]},
        headers=headers,
    )
    assert item.status_code == 200, item.text
    if assign_headers:
        assert client.post(f"/items/{item.json()['id']}/assign", headers=assign_headers).status_code == 200
    return item.json()


def del_me(client, headers, password="password123"):
    return _delete_json(client, headers, {"current_password": password})


def test_delete_requires_correct_password(client, auth_headers):
    headers = auth_headers("traveller")
    # невірний пароль -> 400, акаунт живий
    assert _delete_json(client, headers, {"current_password": "wrong"}).status_code == 400
    # відсутній пароль -> 422 (валідація Pydantic)
    assert _delete_json(client, headers, {}).status_code == 422
    assert client.get("/users/me", headers=headers).status_code == 200


def test_owner_delete_cascades_trips(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org, "Власна поїздка")
    join_by_invite(client, org, guest, trip["id"])
    # гість бере річ орга
    add_item(client, org, trip["id"], "Палатка", assign_headers=guest)

    r = del_me(client, org)
    assert r.status_code == 200, r.text

    # стара сесія й логін недійсні
    assert client.get("/users/me", headers=org).status_code == 401
    assert client.post("/login", data={"username": "org", "password": "password123"}).status_code == 401
    # поїздка пішла разом із власником (у гостя більше немає поїздок)
    assert client.get("/trips/", headers=guest).json()["total"] == 0


def test_participant_delete_cleans_foreign_trip(client, auth_headers):
    org = auth_headers("org")
    user = auth_headers("user")
    trip = create_trip(client, org, "Чужа для user")
    join_by_invite(client, org, user, trip["id"])

    cat = client.post(f"/trips/{trip['id']}/categories/", json={"name": "Спорядження"}, headers=org)
    cat_id = cat.json()["id"]
    # user створює річ, орг створює річ, яку брав user
    user_item = client.post("/items/", json={"name": "Палатка", "quantity": 1, "trip_id": trip["id"], "category_id": cat_id}, headers=user)
    org_item = client.post("/items/", json={"name": "Плитка", "quantity": 1, "trip_id": trip["id"], "category_id": cat_id}, headers=org)
    user_item_id = user_item.json()["id"]
    org_item_id = org_item.json()["id"]
    assert client.post(f"/items/{org_item_id}/assign", headers=user).status_code == 200
    assert client.post(f"/items/{user_item_id}/assign", headers=org).status_code == 200

    assert del_me(client, user).status_code == 200

    trip_data = client.get(f"/trips/{trip['id']}", headers=org).json()
    assert not any(p["username"] == "user" for p in trip_data["participants"])

    items = client.get(f"/trips/{trip['id']}/items/", headers=org).json()["items"]
    palatka = next(i for i in items if i["id"] == user_item_id)
    piltka = next(i for i in items if i["id"] == org_item_id)
    # річ, яку створив user, лишилась, але created_by став null
    assert palatka["created_by"] is None
    # річ, яку брав user, звільнилась
    assert piltka["assignments"] == []

    assert client.get("/users/me", headers=user).status_code == 401
    assert client.post("/login", data={"username": "user", "password": "password123"}).status_code == 401