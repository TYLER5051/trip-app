"""
Тести профілю користувача.

  - GET /users/me без токена → 401;
  - GET /users/me повертає username та лічильники: створені поїздки,
    участь (приєднані, але не власні) та доручені речі;
  - PATCH /users/me/password: невірний старий пароль → 400, вірний → зміна;
  - GET /trips/?role=owned|joined фільтрує список поїздок для табів профілю.
"""


def create_trip(client, headers, title="Похід"):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def join_by_invite(client, org_headers, guest_headers, trip_id):
    token = client.get(f"/trips/{trip_id}/invite", headers=org_headers).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=guest_headers)
    assert r.status_code == 200, r.text


def get_me(client, headers=None):
    r = client.get("/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_me_requires_auth(client):
    assert client.get("/users/me").status_code == 401


def test_me_returns_username_and_zero_counts(client, auth_headers):
    headers = auth_headers("traveller")
    data = get_me(client, headers)

    assert data["username"] == "traveller"
    assert data["owned_trips_count"] == 0
    assert data["participating_trips_count"] == 0
    assert data["assigned_items_count"] == 0


def test_me_counts_owned_and_participating(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")

    create_trip(client, org, "Моя поїздка 1")
    create_trip(client, org, "Моя поїздка 2")
    guest_trip = create_trip(client, guest, "Чужа поїздка")
    join_by_invite(client, guest, org, guest_trip["id"])

    data = get_me(client, org)
    assert data["owned_trips_count"] == 2
    assert data["participating_trips_count"] == 1
    assert data["assigned_items_count"] == 0


def test_me_counts_assigned_items(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)

    cat = client.post(
        f"/trips/{trip['id']}/categories/", json={"name": "Спорядження"}, headers=org
    )
    assert cat.status_code == 200, cat.text

    item = client.post(
        "/items/",
        json={"name": "Палатка", "quantity": 2, "trip_id": trip["id"], "category_id": cat.json()["id"]},
        headers=org,
    )
    assert item.status_code == 200, item.text

    assert client.post(f"/items/{item.json()['id']}/assign", headers=org).status_code == 200

    data = get_me(client, org)
    assert data["assigned_items_count"] == 1


def test_me_change_password(client, auth_headers):
    headers = auth_headers("traveller")

    r = client.patch(
        "/users/me/password",
        json={"old_password": "wrong-old", "new_password": "newpassword123"},
        headers=headers,
    )
    assert r.status_code == 400

    r = client.patch(
        "/users/me/password",
        json={"old_password": "password123", "new_password": "newpassword123"},
        headers=headers,
    )
    assert r.status_code == 200

    # Старий пароль більше не працює, новий — працює.
    assert client.post(
        "/login", data={"username": "traveller", "password": "password123"}
    ).status_code == 401
    assert client.post(
        "/login", data={"username": "traveller", "password": "newpassword123"}
    ).status_code == 200


def test_trips_role_filter(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")

    owned = [create_trip(client, org, f"Власна {i}") for i in (1, 2)]
    guest_trip = create_trip(client, guest, "Чужа")
    join_by_invite(client, guest, org, guest_trip["id"])

    res = client.get("/trips/", headers=org, params={"role": "owned"}).json()
    assert res["total"] == 2
    assert sorted(t["id"] for t in res["items"]) == sorted(t["id"] for t in owned)

    res = client.get("/trips/", headers=org, params={"role": "joined"}).json()
    assert res["total"] == 1
    assert [t["id"] for t in res["items"]] == [guest_trip["id"]]

    assert client.get("/trips/", headers=org, params={"role": "admin"}).status_code == 422