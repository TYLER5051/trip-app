"""
Тести прав доступу до речей.

Правила бізнес-логіки:
  - перейменовувати/видаляти річ може ТІЛЬКИ її автор (created_by) або організатор поїздки;
  - «взяти» (assign) може будь-який учасник, але взяття НЕ дає права редагувати/видаляти;
  - важливу річ (is_critical) не може видалити НІХТО, доки автор або організатор не зніме мітку.
"""

def setup_trip(client, auth_headers):
    """Організатор + два учасники + поїздка з категорією."""
    org = auth_headers("org_demo")
    u1 = auth_headers("p_one")
    u2 = auth_headers("p_two")

    trip_id = client.post("/trips/", json={"title": "Похід"}, headers=org).json()["id"]
    cat = client.post(f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=org).json()

    invite_token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    for headers in (u1, u2):
        r = client.post(f"/trips/invite/{invite_token}", headers=headers)
        assert r.status_code == 200, r.text

    return trip_id, cat["id"], org, u1, u2


def create_item(client, headers, trip_id, category_id, name):
    r = client.post("/items/", json={"name": name, "trip_id": trip_id, "category_id": category_id}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def rename(client, headers, item_id, name):
    return client.patch(f"/items/{item_id}", json={"name": name}, headers=headers)


def delete(client, headers, item_id):
    return client.delete(f"/items/{item_id}", headers=headers)


def assign(client, headers, item_id):
    return client.post(f"/items/{item_id}/assign", headers=headers)


def unassign(client, headers, item_id):
    return client.delete(f"/items/{item_id}/assign", headers=headers)


def test_response_contains_creator(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat_id, "Спальник")
    assert item["created_by"]["username"] == "p_one"


def test_creator_renames_own_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat_id, "Спальник")

    r = rename(client, u1, item["id"], "Спальник-2")
    assert r.status_code == 200
    assert r.json()["name"] == "Спальник-2"


def test_creator_deletes_own_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat_id, "Кросівки")

    assert delete(client, u1, item["id"]).status_code == 200


def test_organizer_renames_participant_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat_id, "Спальник")

    r = rename(client, org, item["id"], "Спальник-макс")
    assert r.status_code == 200
    assert r.json()["name"] == "Спальник-макс"


def test_participant_cannot_rename_organizer_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat_id, "Намет")

    assert rename(client, u1, item["id"], "Хак").status_code == 403


def test_participant_cannot_delete_organizer_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat_id, "Намет")

    assert delete(client, u1, item["id"]).status_code == 403


def test_taker_cannot_rename_or_delete_taken_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat_id, "Намет")

    # u1 бере річ — галочку може ставити будь-який учасник
    assert assign(client, u1, item["id"]).status_code == 200

    # але «взяте» не означає «своє»: перейменувати/видалити заборонено
    assert rename(client, u1, item["id"], "Хак").status_code == 403
    assert delete(client, u1, item["id"]).status_code == 403


def test_organizer_deletes_any_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat_id, "Каремат")

    assert delete(client, org, item["id"]).status_code == 200


def test_participant_cannot_modify_foreign_participant_item(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat_id, "Спальник")

    assert rename(client, u2, item["id"], "Хак").status_code == 403
    assert delete(client, u2, item["id"]).status_code == 403


def test_take_and_unpack_flow(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat_id, "Намет")

    # вільну річ може взяти будь-який учасник
    assert assign(client, u1, item["id"]).status_code == 200

    # кількість вичерпана (quantity=1) — інший учасник взяти не може
    assert assign(client, u2, item["id"]).status_code == 400

    # той, хто взяв, знімає СВОЄ «взяття»
    assert unassign(client, u1, item["id"]).status_code == 200


def test_outsider_cannot_rename(client, auth_headers):
    trip_id, cat_id, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat_id, "Намет")

    outsider = auth_headers("outsider")
    assert rename(client, outsider, item["id"], "Хак").status_code == 403
