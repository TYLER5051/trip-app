"""
Тести Фічі 6: перенесення речей між категоріями (PATCH /items/{id} category_id).

  - переміщення в іншу категорію (організатором і автором речі);
  - переміщення в «Інше» через явний null (category_id = null), без зачіпання інших полів;
  - чужий учасник не може переносити чужу річ (ні в категорію, ні в «Інше») → 403;
  - категорія з іншої поїздки → 400.
"""


def create_trip(client, headers, title):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def join_trip(client, headers, trip_id, owner_headers):
    token = client.get(f"/trips/{trip_id}/invite", headers=owner_headers).json()["invite_token"]
    assert client.post(f"/trips/invite/{token}", headers=headers).status_code == 200


def create_category(client, headers, trip_id, name):
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def create_item(client, headers, trip_id, category_id, name):
    r = client.post(
        "/items/",
        json={"name": name, "trip_id": trip_id, "category_id": category_id, "is_critical": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def setup(client, auth_headers):
    org = auth_headers("move_org")
    u1 = auth_headers("move_u1")
    u2 = auth_headers("move_u2")

    trip = create_trip(client, org, "Похід")
    cat1 = create_category(client, org, trip["id"], "Спорядження")
    cat2 = create_category(client, org, trip["id"], "Харчі")
    for h in (u1, u2):
        join_trip(client, h, trip["id"], org)

    item = create_item(client, u1, trip["id"], cat1["id"], "Спальник")
    return trip, cat1, cat2, org, u1, u2, item


def test_move_to_another_category_by_owner(client, auth_headers):
    trip, cat1, cat2, org, u1, u2, item = setup(client, auth_headers)
    r = client.patch(f"/items/{item['id']}", json={"category_id": cat2["id"]}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["category"]["id"] == cat2["id"]
    assert r.json()["category_id"] == cat2["id"]


def test_move_to_another_category_by_creator(client, auth_headers):
    trip, cat1, cat2, org, u1, u2, item = setup(client, auth_headers)
    r = client.patch(f"/items/{item['id']}", json={"category_id": cat2["id"]}, headers=u1)
    assert r.status_code == 200, r.text
    assert r.json()["category"]["id"] == cat2["id"]


def test_move_to_uncategorized_with_null(client, auth_headers):
    trip, cat1, cat2, org, u1, u2, item = setup(client, auth_headers)
    r = client.patch(f"/items/{item['id']}", json={"category_id": None}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["category"] is None
    assert r.json()["category_id"] is None


def test_explicit_null_preserves_other_fields(client, auth_headers):
    trip, cat1, cat2, org, u1, u2, item = setup(client, auth_headers)
    r = client.patch(
        f"/items/{item['id']}",
        json={"category_id": None, "note": "новина", "quantity": 4},
        headers=org,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["category"] is None
    assert data["note"] == "новина"
    assert data["quantity"] == 4
    assert data["is_critical"] is True  # не змінюється


def test_move_blocked_for_other_participant(client, auth_headers):
    trip, cat1, cat2, org, u1, u2, item = setup(client, auth_headers)
    # чужий учасник не може перенести річ
    r = client.patch(f"/items/{item['id']}", json={"category_id": cat2["id"]}, headers=u2)
    assert r.status_code == 403
    # так само не може скинути категорію в «Інше»
    r = client.patch(f"/items/{item['id']}", json={"category_id": None}, headers=u2)
    assert r.status_code == 403


def test_category_from_other_trip_rejected(client, auth_headers):
    trip, cat1, cat2, org, u1, u2, item = setup(client, auth_headers)
    other = create_trip(client, org, "Інша поїздка")
    other_cat = create_category(client, org, other["id"], "Чужі речі")
    r = client.patch(f"/items/{item['id']}", json={"category_id": other_cat["id"]}, headers=org)
    assert r.status_code == 400