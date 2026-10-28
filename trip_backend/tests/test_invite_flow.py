"""
Тести безпечнішого приєднання за інвайт-токеном замість голого id.

  - токен генерується при створенні поїздки і доступний лише організатору;
  - приєднатися можна лише за токеном (POST /trips/invite/{token});
  - легасі-приєднання за id (POST /trips/{id}/join) більше не існує (404);
  - повторне приєднання / приєднання організатора / невалідний токен — помилка;
  - ротація робить старий токен недійсним;
  - прев'ю поїздки доступне і за токеном (для сторінки входу).
"""


def create_trip(client, headers):
    r = client.post("/trips/", json={"title": "Похід"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def invite_token_of(client, trip_id, headers):
    r = client.get(f"/trips/{trip_id}/invite", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["invite_token"]


def test_join_by_invite_token(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")

    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)
    assert len(token) >= 32

    r = client.post(f"/trips/invite/{token}", headers=guest)
    assert r.status_code == 200, r.text
    assert r.json()["trip_id"] == trip["id"]

    trips = client.get("/trips/", headers=guest).json()
    assert [t["id"] for t in trips] == [trip["id"]]


def test_join_requires_authenticated_user(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    assert client.post(f"/trips/invite/{token}").status_code == 401


def test_duplicate_join_rejected(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 200
    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 400


def test_owner_cannot_join_own_trip(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    assert client.post(f"/trips/invite/{token}", headers=org).status_code == 400


def test_invalid_token_returns_404(client, auth_headers):
    org = auth_headers("org")
    assert client.post("/trips/invite/not_a_real_token", headers=org).status_code == 404


def test_only_owner_can_get_invite_token(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)

    assert client.get(f"/trips/{trip['id']}/invite", headers=guest).status_code == 403


def test_rotate_token_invalidates_old(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    new_token = client.post(f"/trips/{trip['id']}/invite", headers=org).json()["invite_token"]
    assert new_token != token

    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 404
    assert client.post(f"/trips/invite/{new_token}", headers=guest).status_code == 200


def test_preview_by_invite_token(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    r = client.get(f"/trips/invite/{token}/preview")
    assert r.status_code == 200
    assert r.json()["title"] == "Похід"

    assert client.get("/trips/invite/wrong-token/preview").status_code == 404


def test_legacy_join_by_id_is_gone(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)

    assert client.post(f"/trips/{trip['id']}/join", headers=org).status_code == 404


def test_outsider_cannot_read_trip_details(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)

    assert client.get(f"/trips/{trip['id']}", headers=guest).status_code == 403
    assert client.get(f"/trips/{trip['id']}/categories/", headers=guest).status_code == 403


def test_participant_can_read_trip_details(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)
    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 200

    assert client.get(f"/trips/{trip['id']}", headers=guest).status_code == 200
    assert client.get(f"/trips/{trip['id']}/categories/", headers=guest).status_code == 200