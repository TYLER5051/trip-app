"""
Режим «тільки читання» для архівованих поїздок:
  - усі мутації (речі, категорії, призначення, оновлення поїздки, інвайти,
    передача власника, копіювання В архів) → 400;
  - копіювання З архіву в активну поїздку та розархівація → 200;
  - читання архіву (GET поїздки/речей) працює.
"""


def setup_archived(client, auth_headers):
    org = auth_headers("arch_org")
    u1 = auth_headers("arch_u1")
    u2 = auth_headers("arch_u2")

    trip_id = client.post("/trips/", json={"title": "Архівний похід"}, headers=org).json()["id"]
    cat = client.post(f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=org).json()
    item = client.post(
        "/items/",
        json={"name": "Намет", "trip_id": trip_id, "category_id": cat["id"], "quantity": 5},
        headers=org,
    ).json()

    token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    assert client.post(f"/trips/invite/{token}", headers=u1).status_code == 200
    assert client.post(f"/items/{item['id']}/assign", json={"quantity": 1}, headers=u1).status_code == 200
    # u2 теж учасник — і все одно не може мутувати архів
    assert client.post(f"/trips/invite/{token}", headers=u2).status_code == 200

    r = client.post(f"/trips/{trip_id}/archive", headers=org)
    assert r.status_code == 200, r.text

    return trip_id, cat["id"], item["id"], org, u1, u2


def test_add_item_to_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.post("/items/", json={"name": "Сокира", "trip_id": trip_id, "category_id": cat_id}, headers=org)
    assert r.status_code == 400


def test_update_item_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.patch(f"/items/{item_id}", json={"note": "новий"}, headers=org)
    assert r.status_code == 400


def test_delete_item_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.delete(f"/items/{item_id}", headers=org)
    assert r.status_code == 400


def test_assign_item_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.post(f"/items/{item_id}/assign", json={"quantity": 1}, headers=u2)
    assert r.status_code == 400


def test_unassign_item_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.delete(f"/items/{item_id}/assign", headers=u1)
    assert r.status_code == 400


def test_create_category_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": "Харчі"}, headers=org)
    assert r.status_code == 400


def test_update_category_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.patch(f"/trips/{trip_id}/categories/{cat_id}", json={"name": "Інше"}, headers=org)
    assert r.status_code == 400


def test_delete_category_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.delete(f"/trips/{trip_id}/categories/{cat_id}", headers=org)
    assert r.status_code == 400


def test_update_trip_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.patch(f"/trips/{trip_id}", json={"title": "Нова назва"}, headers=org)
    assert r.status_code == 400


def test_rotate_invite_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.post(f"/trips/{trip_id}/invite", headers=org)
    assert r.status_code == 400


def test_join_archived_by_invite_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=u2)
    assert r.status_code == 400


def test_transfer_owner_in_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    u1_id = client.get("/users/me", headers=u1).json()["id"]
    r = client.patch(f"/trips/{trip_id}/transfer-owner", json={"new_owner_id": u1_id}, headers=org)
    assert r.status_code == 400


def test_copy_items_into_archived_rejected(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    active = client.post("/trips/", json={"title": "Активна"}, headers=org).json()
    r = client.post(f"/trips/{trip_id}/copy-items", json={"source_trip_id": active["id"]}, headers=org)
    assert r.status_code == 400


def test_copy_items_from_archived_to_active_ok(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    active = client.post("/trips/", json={"title": "Активна"}, headers=org).json()
    r = client.post(f"/trips/{active['id']}/copy-items", json={"source_trip_id": trip_id}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["copied_items"] == 1


def test_unarchive_archived_trip_ok(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    r = client.post(f"/trips/{trip_id}/unarchive", headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["is_archived"] is False


def test_read_archived_trip_still_works(client, auth_headers):
    trip_id, cat_id, item_id, org, u1, u2 = setup_archived(client, auth_headers)
    assert client.get(f"/trips/{trip_id}", headers=org).status_code == 200
    assert client.get(f"/trips/{trip_id}/items/?limit=100", headers=org).status_code == 200