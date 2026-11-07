"""
Тести профілю користувача.

  - GET /users/me без токена → 401;
  - GET /users/me повертає username та лічильники: створені поїздки,
    участь (приєднані, але не власні) та доручені речі;
  - PATCH /users/me/password: невірний старий пароль → 400, вірний → зміна;
  - GET /trips/?role=owned|joined фільтрує список поїздок для табів профілю.
"""


import auth
from jose import jwt


def _user_id(client, headers):
    return client.get("/users/me", headers=headers).json()["id"]


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
    assert data["total_items_count"] == 0
    assert data["packed_items_count"] == 0


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

def _patch_me(client, headers, **payload):
    return client.patch("/users/me", json=payload, headers=headers)


def test_me_patch_requires_auth(client):
    assert client.patch("/users/me", json={}).status_code == 401


def _add_category_item(client, headers, trip_id, name, assign_headers=None):
    # Категорія «Спорядження» унікальна в межах поїздки (trip_id, name);
    # перевикористовуємо наявну, щоб можна було додати кілька речей в одну поїздку.
    cats = client.get(f"/trips/{trip_id}/categories/", headers=headers).json()
    cat = next((c for c in cats if c["name"] == "Спорядження"), None)
    if cat is None:
        r = client.post(
            f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=headers
        )
        assert r.status_code == 200, r.text
        cat = r.json()
    item = client.post(
        "/items/",
        json={"name": name, "trip_id": trip_id, "category_id": cat["id"]},
        headers=headers,
    )
    assert item.status_code == 200, item.text
    if assign_headers is not None:
        r = client.post(f"/items/{item.json()['id']}/assign", headers=assign_headers)
        assert r.status_code == 200, r.text
    return item.json()


def test_me_packing_stats_aggregate(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    helper = auth_headers("helper")

    owned = create_trip(client, org, "Власна")
    guest_trip = create_trip(client, guest, "Гостьова")
    join_by_invite(client, guest, org, guest_trip["id"])
    join_by_invite(client, guest, helper, guest_trip["id"])

    # Власна поїздка: 2 речі — одна взята оргом, одна вільна.
    _add_category_item(client, org, owned["id"], "Палатка")
    _add_category_item(client, org, owned["id"], "Плитка", assign_headers=org)

    # Гостьова поїздка: 1 річ, взята іншим учасником (helper).
    _add_category_item(client, guest, guest_trip["id"], "Каремат", assign_headers=helper)

    data = get_me(client, org)
    # total = всі речі в поїздках (власні + приєднані).
    assert data["total_items_count"] == 3
    # packed = речі з БУДЬ-ЯКИМ призначенням (навіть чужим).
    assert data["packed_items_count"] == 2
    # призначені саме оргу — окрема метрика.
    assert data["assigned_items_count"] == 1


def test_me_packing_stats_excludes_foreign_trips(client, auth_headers):
    org = auth_headers("org")
    foreign = auth_headers("foreign")
    foreign_trip = create_trip(client, foreign, "Чужа мені")
    _add_category_item(client, foreign, foreign_trip["id"], "Своя річ", assign_headers=foreign)

    data = get_me(client, org)
    assert data["total_items_count"] == 0
    assert data["packed_items_count"] == 0
    assert data["assigned_items_count"] == 0


def test_me_change_username_issues_new_token(client, auth_headers):
    headers = auth_headers("old_username")
    r = _patch_me(client, headers, username="new_username", current_password="password123")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["username"] == "new_username"
    assert "access_token" in data

    # Новий токен коректний і містить оновлений username та збережений token_version.
    payload = jwt.decode(data["access_token"], auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == str(_user_id(client, headers))
    assert payload["ver"] == 1
    assert payload["username"] == "new_username"

    # Новий токен працює. Старий також лишається валідним:
    # sub=user.id не змінився, ver не інкрементувався — тому користувача
    # зміна username НЕ «розлогінює» (це бажана поведінка).
    new_headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert client.get("/users/me", headers=new_headers).status_code == 200
    assert client.get("/users/me", headers=headers).status_code == 200

    # Старий логін не працює, новий — працює.
    assert client.post(
        "/login", data={"username": "old_username", "password": "password123"}
    ).status_code == 401
    assert client.post(
        "/login", data={"username": "new_username", "password": "password123"}
    ).status_code == 200


def test_me_change_username_cyrillic_ok(client, auth_headers):
    headers = auth_headers("traveller")
    r = _patch_me(client, headers, username="Олександр", current_password="password123")
    assert r.status_code == 200, r.text
    assert get_me(client, headers)["username"] == "Олександр"


def test_me_change_username_requires_current_password(client, auth_headers):
    headers = auth_headers("traveller")
    r = _patch_me(client, headers, username="new_username")
    assert r.status_code == 400
    assert "поточний пароль" in r.json()["detail"]


def test_me_change_username_wrong_current_password(client, auth_headers):
    headers = auth_headers("traveller")
    r = _patch_me(client, headers, username="new_username", current_password="wrong-pass")
    assert r.status_code == 400
    assert r.json()["detail"] == "Невірний поточний пароль"


def test_me_change_username_too_short_rejected(client, auth_headers):
    headers = auth_headers("traveller")
    r = _patch_me(client, headers, username="ab", current_password="password123")
    assert r.status_code == 422


def test_me_change_username_invalid_chars_rejected(client, auth_headers):
    headers = auth_headers("traveller")
    # Пробіл усередині заборонений.
    assert _patch_me(client, headers, username="new user", current_password="password123").status_code == 422
    # Символ @ заборонений.
    assert _patch_me(client, headers, username="nov@y", current_password="password123").status_code == 422
    # Дефіс та підкреслення — дозволені.
    assert _patch_me(client, headers, username="new_-login", current_password="password123").status_code == 200


def test_me_change_username_conflict(client, auth_headers):
    auth_headers("first")
    headers = auth_headers("second")
    r = _patch_me(client, headers, username="first", current_password="password123")
    assert r.status_code == 400
    assert r.json()["detail"] == "Користувач із таким ім'ям вже існує"


def test_me_update_avatar_color(client, auth_headers):
    headers = auth_headers("traveller")
    r = _patch_me(client, headers, avatar_color="#42b883")
    assert r.status_code == 200, r.text

    me = get_me(client, headers)
    assert me["avatar_color"] == "#42b883"


def test_me_invalid_avatar_color_rejected(client, auth_headers):
    headers = auth_headers("traveller")
    r = _patch_me(client, headers, avatar_color="blue")
    assert r.status_code == 422


def test_me_empty_patch_is_noop(client, auth_headers):
    headers = auth_headers("traveller")
    assert _patch_me(client, headers).status_code == 200
    me = get_me(client, headers)
    assert me["username"] == "traveller"
    assert me["avatar_color"] is None