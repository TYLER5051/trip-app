"""
Тести packing-core: quantity / note / is_critical + дублікати + перенос речей.

Правила:
  - quantity/note/is_critical + перенос у категорію може міняти лише автор або організатор;
  - «взяти» річ (assign) може будь-який учасник, поки є вільні місця (quantity);
  - важливу річ не може видалити ніхто, доки автор/організатор не зніме мітку;
  - дублікат = та сама назва в межах поїздки: створення заборонене (400),
    той самий патерн, що й для категорій.
"""


def setup_trip(client, auth_headers):
    org = auth_headers("org_core")
    u1 = auth_headers("p_one")
    u2 = auth_headers("p_two")

    trip_id = client.post("/trips/", json={"title": "Похід"}, headers=org).json()["id"]
    cat1 = client.post(f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=org).json()
    cat2 = client.post(f"/trips/{trip_id}/categories/", json={"name": "Харчі"}, headers=org).json()
    client.post(f"/trips/{trip_id}/join", headers=u1)
    client.post(f"/trips/{trip_id}/join", headers=u2)

    return trip_id, cat1["id"], cat2["id"], org, u1, u2


def create_item(client, headers, trip_id, category_id, name, **extra):
    body = {"name": name, "trip_id": trip_id, "category_id": category_id, **extra}
    r = client.post("/items/", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def patch(client, headers, item_id, **body):
    return client.patch(f"/items/{item_id}", json=body, headers=headers)


def test_create_with_quantity_note_critical(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник", quantity=2, note="-5°C", is_critical=True)
    assert item["quantity"] == 2
    assert item["note"] == "-5°C"
    assert item["is_critical"] is True


def test_quantity_defaults_to_one(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Кросівки")
    assert item["quantity"] == 1
    assert item["note"] is None
    assert item["is_critical"] is False


def test_create_response_shape(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")
    assert item["name"] == "Спальник"
    assert item["quantity"] == 1
    assert item["category_id"] == cat1


def test_duplicate_in_same_category_rejected(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    create_item(client, u1, trip_id, cat1, "Спальник")
    r = client.post("/items/", json={"name": "Спальник", "trip_id": trip_id, "category_id": cat1}, headers=u2)
    assert r.status_code == 400


def test_different_case_or_extra_spaces_not_duplicate(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    create_item(client, u1, trip_id, cat1, "Спальник")
    item = create_item(client, u2, trip_id, cat1, "  спальник ")
    assert item["name"] == "  спальник "


def test_same_name_in_other_category_is_also_rejected(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    create_item(client, u1, trip_id, cat1, "Спальник")
    r = client.post("/items/", json={"name": "Спальник", "trip_id": trip_id, "category_id": cat2}, headers=u2)
    assert r.status_code == 400


def test_same_name_in_other_trip_is_allowed(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    create_item(client, u1, trip_id, cat1, "Спальник")

    outsider = auth_headers("outsider_other")
    other_trip = client.post("/trips/", json={"title": "Інша"}, headers=outsider).json()["id"]
    other_cat = client.post(f"/trips/{other_trip}/categories/", json={"name": "Спорядження"}, headers=outsider).json()

    item = create_item(client, outsider, other_trip, other_cat["id"], "Спальник")
    assert item["name"] == "Спальник"


def test_author_updates_quantity_note_critical(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")
    r = patch(client, u1, item["id"], quantity=3, note="каремат окремо", is_critical=True)
    assert r.status_code == 200
    data = r.json()
    assert data["quantity"] == 3
    assert data["note"] == "каремат окремо"
    assert data["is_critical"] is True


def test_organizer_updates_participant_item(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")
    r = patch(client, org, item["id"], quantity=4)
    assert r.status_code == 200
    assert r.json()["quantity"] == 4


def test_participant_cannot_update_quantity(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Намет")
    assert patch(client, u1, item["id"], quantity=9).status_code == 403


def test_participant_cannot_move_foreign_item(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Намет")
    assert patch(client, u1, item["id"], category_id=cat2).status_code == 403


def test_author_moves_item_to_other_category(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")
    r = patch(client, u1, item["id"], category_id=cat2)
    assert r.status_code == 200
    assert r.json()["category_id"] == cat2


def test_rename_to_existing_name_in_trip_rejected(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    create_item(client, u1, trip_id, cat1, "Спальник")
    item2 = create_item(client, u2, trip_id, cat1, "Намет")

    assert patch(client, u2, item2["id"], name="Спальник").status_code == 400


def test_move_to_missing_category_404(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")
    assert patch(client, u1, item["id"], category_id=99999).status_code == 404


def test_move_to_foreign_trip_category_400(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")

    outsider = auth_headers("outsider_core")
    other_trip = client.post("/trips/", json={"title": "Інша"}, headers=outsider).json()["id"]
    foreign_cat = client.post(f"/trips/{other_trip}/categories/", json={"name": "Чуже"}, headers=outsider).json()["id"]

    assert patch(client, u1, item["id"], category_id=foreign_cat).status_code == 400


def test_invalid_quantity_zero_422(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник")
    assert patch(client, u1, item["id"], quantity=0).status_code == 422


def test_clear_note_with_empty_string(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Спальник", note="було")
    r = patch(client, u1, item["id"], note="")
    assert r.status_code == 200
    assert r.json()["note"] == ""


def test_participant_can_assign_and_unassign(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Намет")
    assert client.post(f"/items/{item['id']}/assign", headers=u1).status_code == 200
    assert client.delete(f"/items/{item['id']}/assign", headers=u1).status_code == 200


def test_assign_up_to_quantity(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка", quantity=2)
    assert client.post(f"/items/{item['id']}/assign", headers=u1).status_code == 200
    assert client.post(f"/items/{item['id']}/assign", headers=u2).status_code == 200
    # кількість вичерпана — навіть організатор взяти не може
    assert client.post(f"/items/{item['id']}/assign", headers=org).status_code == 400


def test_assign_same_user_twice_rejected(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка", quantity=3)
    assert client.post(f"/items/{item['id']}/assign", headers=u1).status_code == 200
    assert client.post(f"/items/{item['id']}/assign", headers=u1).status_code == 400


def test_unassign_when_not_assigned_400(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка")
    assert client.delete(f"/items/{item['id']}/assign", headers=u1).status_code == 400


def test_assign_by_outsider_403(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка")
    outsider = auth_headers("outsider_assign")
    assert client.post(f"/items/{item['id']}/assign", headers=outsider).status_code == 403


def test_assigned_users_in_response(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка")
    client.post(f"/items/{item['id']}/assign", headers=u1)

    trip = client.get(f"/trips/{trip_id}", headers=org).json()
    stored = next(i for i in trip["items"] if i["id"] == item["id"])
    assert [a["username"] for a in stored["assigned_users"]] == ["p_one"]


def test_owner_can_take_item(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Палатка")
    assert client.post(f"/items/{item['id']}/assign", headers=org).status_code == 200


def test_critical_item_cannot_be_deleted_by_anyone(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Аптечка", is_critical=True)
    assert client.delete(f"/items/{item['id']}", headers=u1).status_code == 400
    assert client.delete(f"/items/{item['id']}", headers=org).status_code == 400


def test_creator_unmarks_critical_then_deletes(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Аптечка", is_critical=True)
    assert patch(client, u1, item["id"], is_critical=False).status_code == 200
    assert client.delete(f"/items/{item['id']}", headers=u1).status_code == 200


def test_organizer_unmarks_critical_then_deletes(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Аптечка", is_critical=True)
    assert patch(client, org, item["id"], is_critical=False).status_code == 200
    assert client.delete(f"/items/{item['id']}", headers=org).status_code == 200


def test_participant_cannot_unmark_critical(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Аптечка", is_critical=True)
    assert patch(client, u2, item["id"], is_critical=False).status_code == 403


def test_quantity_editable_after_creation(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, u1, trip_id, cat1, "Палатка")
    r = patch(client, u1, item["id"], quantity=3)
    assert r.status_code == 200
    assert r.json()["quantity"] == 3


def test_remove_participant_clears_assignments(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка", quantity=2)
    client.post(f"/items/{item['id']}/assign", headers=u2)

    trip = client.get(f"/trips/{trip_id}", headers=org).json()
    u2_id = next(p["id"] for p in trip["participants"] if p["username"] == "p_two")

    assert client.delete(f"/trips/{trip_id}/participants/{u2_id}", headers=org).status_code == 200

    trip = client.get(f"/trips/{trip_id}", headers=org).json()
    stored = next(i for i in trip["items"] if i["id"] == item["id"])
    assert stored["assigned_users"] == []

