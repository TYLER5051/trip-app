"""Тести передачі прав організатора (PATCH /trips/{id}/transfer-owner)."""


def create_trip(client, headers):
    r = client.post("/trips/", json={"title": "Похід"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _user_id(client, headers):
    return client.get("/users/me", headers=headers).json()["id"]


def _join(client, guest, org, trip_id):
    token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 200


def transfer(client, headers, trip_id, new_owner_id):
    return client.patch(f"/trips/{trip_id}/transfer-owner",
                        json={"new_owner_id": new_owner_id}, headers=headers)


def test_successful_transfer_swaps_roles(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    _join(client, guest, org, trip["id"])

    r = transfer(client, org, trip["id"], _user_id(client, guest))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["owner"]["username"] == "guest"
    assert [p["username"] for p in data["participants"]] == ["org"]


def test_only_current_owner_can_transfer(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    outsider = auth_headers("outsider")
    trip = create_trip(client, org)
    _join(client, guest, org, trip["id"])
    guest_id = _user_id(client, guest)

    # учасник не може передавати
    assert transfer(client, guest, trip["id"], guest_id).status_code == 403
    # сторонній — теж не може
    assert transfer(client, outsider, trip["id"], guest_id).status_code == 403


def test_transfer_trip_not_found(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    assert transfer(client, org, 99999, _user_id(client, guest)).status_code == 404


def test_transfer_to_self_rejected(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)
    assert transfer(client, org, trip["id"], _user_id(client, org)).status_code == 400


def test_transfer_to_non_participant_rejected(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    assert transfer(client, org, trip["id"], _user_id(client, guest)).status_code == 400


def test_transfer_to_unknown_user_rejected(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)
    assert transfer(client, org, trip["id"], 99999).status_code == 404


def test_new_owner_can_manage_and_old_becomes_member(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    _join(client, guest, org, trip["id"])
    guest_id = _user_id(client, guest)

    assert transfer(client, org, trip["id"], guest_id).status_code == 200

    # новий організатор може отримати / перекинути інвайт-токен
    assert client.get(f"/trips/{trip['id']}/invite", headers=guest).status_code == 200
    assert client.post(f"/trips/{trip['id']}/invite", headers=guest).status_code == 200

    # старий організатор тепер учасник: може бачити, але не видаляти поїздку
    assert client.get(f"/trips/{trip['id']}", headers=org).status_code == 200
    assert client.delete(f"/trips/{trip['id']}", headers=org).status_code == 403

    # у списку гостя поїздка тепер «створена» (owned), у орга — «приєднана»
    owned = client.get("/trips/?role=owned", headers=guest).json()
    assert [t["id"] for t in owned["items"]] == [trip["id"]]
    joined = client.get("/trips/?role=joined", headers=org).json()
    assert [t["id"] for t in joined["items"]] == [trip["id"]]