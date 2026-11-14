"""
Тести Фічі 17: перенесення речей при видаленні категорії (DELETE ?move_to=).

  - move_to: речі переносяться у вказану категорію, а не в «Інше»; повідомлення з назвою цілі;
  - без move_to: речі в «Інше» (регресія — раніше тут був AttributeError);
  - move_to = сама категорія / неіснуюча / категорія іншої поїздки → 400;
  - порожня категорія з move_to все одно видаляється (200);
  - автор категорії може видаляти з move_to.
"""


def setup_trip(client, auth_headers):
    org = auth_headers("org_del")
    u1 = auth_headers("p_one")
    u2 = auth_headers("p_two")
    trip_id = client.post("/trips/", json={"title": "Похід"}, headers=org).json()["id"]

    invite_token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    for headers in (u1, u2):
        r = client.post(f"/trips/invite/{invite_token}", headers=headers)
        assert r.status_code == 200, r.text

    cat_a = client.post(f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=org).json()
    cat_b = client.post(f"/trips/{trip_id}/categories/", json={"name": "Харчі"}, headers=org).json()
    return trip_id, org, u1, u2, cat_a, cat_b


def make_item(client, headers, trip_id, category_id, name):
    r = client.post(
        "/items/",
        json={"name": name, "trip_id": trip_id, "category_id": category_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def delete_cat(client, headers, trip_id, cat_id, move_to=None):
    params = None if move_to is None else {"move_to": move_to}
    return client.delete(f"/trips/{trip_id}/categories/{cat_id}", params=params, headers=headers)


def load_items(client, headers, trip_id):
    return client.get(f"/trips/{trip_id}/items/", headers=headers).json()["items"]


def test_delete_with_move_to_moves_items_to_target(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)
    first = make_item(client, org, trip_id, cat_a["id"], "Намет")
    second = make_item(client, org, trip_id, cat_a["id"], "Каремат")

    r = delete_cat(client, org, trip_id, cat_a["id"], move_to=cat_b["id"])
    assert r.status_code == 200, r.text
    assert "Харчі" in r.json()["message"]
    assert "2" in r.json()["message"]

    items = load_items(client, org, trip_id)
    assert len(items) == 2
    assert {i["id"] for i in items} == {first["id"], second["id"]}
    assert all(i["category_id"] == cat_b["id"] for i in items)


def test_delete_without_move_to_moves_to_other_and_no_crash(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)
    make_item(client, org, trip_id, cat_a["id"], "Намет")

    r = delete_cat(client, org, trip_id, cat_a["id"])
    assert r.status_code == 200, r.text
    assert "«Інше»" in r.json()["message"]

    items = load_items(client, org, trip_id)
    assert all(i["category_id"] is None for i in items)


def test_delete_with_move_to_same_category_rejected(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)
    r = delete_cat(client, org, trip_id, cat_a["id"], move_to=cat_a["id"])
    assert r.status_code == 400


def test_delete_with_move_to_unknown_category_rejected(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)
    r = delete_cat(client, org, trip_id, cat_a["id"], move_to=99999)
    assert r.status_code == 400


def test_delete_with_move_to_foreign_trip_category_rejected(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)

    outsider = auth_headers("outsider")
    other_trip = client.post("/trips/", json={"title": "Інша"}, headers=outsider).json()["id"]
    other_cat = client.post(
        f"/trips/{other_trip}/categories/", json={"name": "Чуже"}, headers=outsider
    ).json()

    r = delete_cat(client, org, trip_id, cat_a["id"], move_to=other_cat["id"])
    assert r.status_code == 400


def test_delete_empty_category_with_move_to_is_ok(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)
    empty = client.post(f"/trips/{trip_id}/categories/", json={"name": "Порожня"}, headers=org).json()

    r = delete_cat(client, org, trip_id, empty["id"], move_to=cat_b["id"])
    assert r.status_code == 200, r.text
    assert "видалено" in r.json()["message"]


def test_creator_can_delete_own_category_with_move_to(client, auth_headers):
    trip_id, org, u1, u2, cat_a, cat_b = setup_trip(client, auth_headers)
    own_cat = client.post(f"/trips/{trip_id}/categories/", json={"name": "Моє"}, headers=u1).json()
    make_item(client, u1, trip_id, own_cat["id"], "Каремат")

    r = client.delete(
        f"/trips/{trip_id}/categories/{own_cat['id']}",
        params={"move_to": cat_b["id"]},
        headers=u1,
    )
    assert r.status_code == 200, r.text
    assert all(i["category_id"] == cat_b["id"] for i in load_items(client, u1, trip_id))