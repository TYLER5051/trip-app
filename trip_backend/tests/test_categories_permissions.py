"""
Тести прав доступу до категорій.

Правила бізнес-логіки:
  - перейменовувати/видаляти категорію може ТІЛЬКИ її автор (created_by) або організатор;
  - дублікат назви перевіряється в межах поїздки (сама себе не рахує);
  - при видаленні категорії її речі переносяться в «Інше» (category_id = NULL).
"""

def setup_trip(client, auth_headers):
    org = auth_headers("org_demo")
    u1 = auth_headers("p_one")
    u2 = auth_headers("p_two")
    trip_id = client.post("/trips/", json={"title": "Похід"}, headers=org).json()["id"]
    client.post(f"/trips/{trip_id}/join", headers=u1)
    client.post(f"/trips/{trip_id}/join", headers=u2)
    return trip_id, org, u1, u2


def make_category(client, headers, trip_id, name):
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def rename_cat(client, headers, trip_id, cat_id, name):
    return client.patch(f"/trips/{trip_id}/categories/{cat_id}", json={"name": name}, headers=headers)


def delete_cat(client, headers, trip_id, cat_id):
    return client.delete(f"/trips/{trip_id}/categories/{cat_id}", headers=headers)


def test_response_contains_creator(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")
    assert cat["created_by"]["username"] == "p_one"


def test_creator_renames_own_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")

    r = rename_cat(client, u1, trip_id, cat["id"], "Продукти")
    assert r.status_code == 200
    assert r.json()["name"] == "Продукти"


def test_organizer_renames_participant_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")

    r = rename_cat(client, org, trip_id, cat["id"], "Провизия")
    assert r.status_code == 200


def test_other_participant_cannot_rename_foreign_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")

    assert rename_cat(client, u2, trip_id, cat["id"], "Хак").status_code == 403


def test_participant_cannot_rename_organizer_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, org, trip_id, "Спорядження")

    assert rename_cat(client, u1, trip_id, cat["id"], "Хак").status_code == 403


def test_rename_to_same_name_is_allowed(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")

    assert rename_cat(client, u1, trip_id, cat["id"], "Харчі").status_code == 200


def test_duplicate_name_within_trip_is_rejected(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    make_category(client, org, trip_id, "Спорядження")
    cat2 = make_category(client, u1, trip_id, "Харчі")

    assert rename_cat(client, u1, trip_id, cat2["id"], "Спорядження").status_code == 400


def test_same_name_in_other_trip_is_allowed(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    make_category(client, org, trip_id, "Спорядження")

    outsider = auth_headers("outsider")
    other_trip = client.post("/trips/", json={"title": "Інша"}, headers=outsider).json()["id"]
    other_cat = make_category(client, outsider, other_trip, "Спорядження")

    # той самий name, але в ІНШІЙ поїздці — не конфлікт
    assert rename_cat(client, outsider, other_trip, other_cat["id"], "Спорядження").status_code == 200


def test_creator_deletes_own_empty_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Порожня")

    assert delete_cat(client, u1, trip_id, cat["id"]).status_code == 200


def test_delete_category_moves_items_to_other(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Інвентар")
    for name in ("Намет", "Каремат"):
        r = client.post("/items/", json={"name": name, "trip_id": trip_id, "category_id": cat["id"]}, headers=u1)
        assert r.status_code == 200

    r = delete_cat(client, u1, trip_id, cat["id"])
    assert r.status_code == 200
    assert "2" in r.json()["message"]  # у відповіді кажемо, скільки речей перенесено

    trip = client.get(f"/trips/{trip_id}", headers=org).json()
    moved = [i for i in trip["items"] if i["name"] in ("Намет", "Каремат")]
    assert len(moved) == 2                       # речі НЕ видаляються...
    assert all(i["category_id"] is None for i in moved)  # ...а переносяться в «Інше»


def test_organizer_deletes_participant_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")

    assert delete_cat(client, org, trip_id, cat["id"]).status_code == 200


def test_participant_cannot_delete_foreign_category(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, u1, trip_id, "Харчі")

    assert delete_cat(client, u2, trip_id, cat["id"]).status_code == 403


def test_outsider_cannot_delete(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)
    cat = make_category(client, org, trip_id, "Спорядження")

    outsider = auth_headers("outsider")
    assert delete_cat(client, outsider, trip_id, cat["id"]).status_code == 403


def test_delete_missing_category_returns_404(client, auth_headers):
    trip_id, org, u1, u2 = setup_trip(client, auth_headers)

    assert delete_cat(client, org, trip_id, 99999).status_code == 404
