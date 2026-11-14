"""
Тести Фічі 16: наслідування речей з минулої поїздки (POST /trips/{id}/copy-items).

  - копіюються категорії (відсутні створюються, наявні перевикористовуються) і речі
    (quantity/note/is_critical), речі з категорією None (після видалення категорії) лишаються без неї;
  - дублікати за назвою в цільовій поїздці пропускаються (skipped);
  - assignments у копії НЕ переносяться; новий created_by = той, хто копіює;
  - копії незалежні від джерела;
  - 400 для source == target, 404 для неіснуючого джерела, 403 без членства у джерелі/цілі.
"""


def create_trip(client, headers, title):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def create_category(client, headers, trip_id, name):
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def create_item(client, headers, trip_id, category_id, name, **extra):
    body = {"name": name, "trip_id": trip_id, "category_id": category_id, **extra}
    r = client.post("/items/", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def join_trip(client, headers, trip_id, owner_headers):
    token = client.get(f"/trips/{trip_id}/invite", headers=owner_headers).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=headers)
    assert r.status_code == 200, r.text


def copy_items(client, headers, target_trip_id, source_trip_id):
    return client.post(
        f"/trips/{target_trip_id}/copy-items",
        json={"source_trip_id": source_trip_id},
        headers=headers,
    )


def setup_source_with_items(client, headers, title="Минулий похід"):
    """Поїздка-джерело: 2 категорії, речі з quantity/note/is_critical + річ без категорії."""
    trip = create_trip(client, headers, title)
    cat1 = create_category(client, headers, trip["id"], "Спорядження")
    cat2 = create_category(client, headers, trip["id"], "Харчі")

    create_item(client, headers, trip["id"], cat1["id"], "Намет", quantity=1, is_critical=True)
    create_item(client, headers, trip["id"], cat2["id"], "Макарони", quantity=3, note="2кг")

    # Річ без категорії: створюємо в категорії, потім видаляємо категорію (→ «Інше»)
    cat3 = create_category(client, headers, trip["id"], "Тимчасова")
    create_item(client, headers, trip["id"], cat3["id"], "Сірники")
    r = client.delete(f"/trips/{trip['id']}/categories/{cat3['id']}", headers=headers)
    assert r.status_code == 200, r.text

    return trip


def load_items(client, headers, trip_id):
    return client.get(f"/trips/{trip_id}/items/", headers=headers).json()["items"]


def test_copy_items_and_categories_to_empty_trip(client, auth_headers):
    org = auth_headers("copy_org")
    source = setup_source_with_items(client, org)
    target = create_trip(client, org, "Новий похід")

    r = copy_items(client, org, target["id"], source["id"])
    assert r.status_code == 200, r.text
    assert r.json()["copied_items"] == 3
    assert r.json()["skipped_items"] == 0

    items = load_items(client, org, target["id"])
    assert {i["name"] for i in items} == {"Намет", "Макарони", "Сірники"}

    by_name = {i["name"]: i for i in items}
    assert by_name["Намет"]["is_critical"] is True
    assert by_name["Макарони"]["quantity"] == 3
    assert by_name["Макарони"]["note"] == "2кг"
    assert all(i["assignments"] == [] for i in items)

    cats = client.get(f"/trips/{target['id']}/categories/", headers=org).json()
    assert {c["name"] for c in cats} == {"Спорядження", "Харчі"}
    cat_names = {c["name"]: c["id"] for c in cats}
    assert by_name["Намет"]["category"]["id"] == cat_names["Спорядження"]
    assert by_name["Макарони"]["category"]["id"] == cat_names["Харчі"]
    assert by_name["Сірники"]["category"] is None


def test_copy_skips_duplicates(client, auth_headers):
    org = auth_headers("copy_dup")
    source = setup_source_with_items(client, org)
    target = create_trip(client, org, "Новий похід")

    cat = create_category(client, org, target["id"], "Спорядження")
    existing = create_item(client, org, target["id"], cat["id"], "Намет", quantity=5)

    r = copy_items(client, org, target["id"], source["id"])
    assert r.status_code == 200, r.text
    assert r.json()["copied_items"] == 2
    assert r.json()["skipped_items"] == 1

    items = load_items(client, org, target["id"])
    assert len(items) == 3
    kept = next(i for i in items if i["name"] == "Намет")
    assert kept["id"] == existing["id"]
def test_copy_reuses_existing_categories(client, auth_headers):
    org = auth_headers("copy_cat")
    source = setup_source_with_items(client, org)
    target = create_trip(client, org, "Новий похід")

    create_category(client, org, target["id"], "Харчі")

    r = copy_items(client, org, target["id"], source["id"])
    assert r.status_code == 200, r.text

    cats = client.get(f"/trips/{target['id']}/categories/", headers=org).json()
    assert {c["name"] for c in cats} == {"Харчі", "Спорядження"}  # лише одна нова

    items = load_items(client, org, target["id"])
    macaroni = next(i for i in items if i["name"] == "Макарони")
    assert macaroni["category"]["name"] == "Харчі"


def test_assignments_not_copied(client, auth_headers):
    org = auth_headers("copy_asg_org")
    guest = auth_headers("copy_asg_guest")
    source = setup_source_with_items(client, org)
    join_trip(client, guest, source["id"], org)

    target = create_trip(client, org, "Новий похід")
    join_trip(client, guest, target["id"], org)

    source_items = load_items(client, org, source["id"])
    hiker = next(i for i in source_items if i["name"] == "Намет")
    assert client.post(f"/items/{hiker['id']}/assign", json={"quantity": 1}, headers=guest).status_code == 200

    r = copy_items(client, org, target["id"], source["id"])
    assert r.status_code == 200, r.text

    target_items = load_items(client, org, target["id"])
    copied = next(i for i in target_items if i["name"] == "Намет")
    assert copied["assignments"] == []
    # джерело не зачеплене
    assert len(load_items(client, org, source["id"])[0]["assignments"]) == 1


def test_copied_items_are_independent(client, auth_headers):
    org = auth_headers("copy_ind")
    source = setup_source_with_items(client, org)
    target = create_trip(client, org, "Новий похід")
    copy_items(client, org, target["id"], source["id"])

    target_namet = next(i for i in load_items(client, org, target["id"]) if i["name"] == "Намет")
    source_namet = next(i for i in load_items(client, org, source["id"]) if i["name"] == "Намет")

    assert client.patch(f"/items/{target_namet['id']}", json={"quantity": 9}, headers=org).status_code == 200
    # важливу річ спершу зневартітити (автор/організатор), інакше видалення заблоковане
    assert client.patch(f"/items/{target_namet['id']}", json={"is_critical": False}, headers=org).status_code == 200
    assert client.delete(f"/items/{target_namet['id']}", headers=org).status_code == 200

    assert len(load_items(client, org, target["id"])) == 2
    source_items = load_items(client, org, source["id"])
    assert len(source_items) == 3
    intact = next(i for i in source_items if i["name"] == "Намет")
    assert intact["quantity"] == 1 and intact["id"] == source_namet["id"]


def test_creator_of_copies_is_current_user(client, auth_headers):
    org = auth_headers("copy_creator_org")
    guest = auth_headers("copy_creator_guest")
    source = setup_source_with_items(client, org)
    join_trip(client, guest, source["id"], org)

    target = create_trip(client, guest, "Новий похід")
    r = copy_items(client, guest, target["id"], source["id"])
    assert r.status_code == 200, r.text

    guest_id = client.get("/users/me", headers=guest).json()["id"]
    items = load_items(client, guest, target["id"])
    assert all(i["created_by"]["id"] == guest_id for i in items)


def test_copy_same_trip_rejected(client, auth_headers):
    org = auth_headers("copy_same")
    trip = create_trip(client, org, "Похід")
    r = copy_items(client, org, trip["id"], trip["id"])
    assert r.status_code == 400


def test_copy_unknown_source_404(client, auth_headers):
    org = auth_headers("copy_404")
    target = create_trip(client, org, "Новий похід")
    r = copy_items(client, org, target["id"], 99999)
    assert r.status_code == 404


def test_copy_requires_membership_of_both_trips(client, auth_headers):
    org = auth_headers("copy_perm_org")
    outsider = auth_headers("copy_perm_out")
    member = auth_headers("copy_perm_member")

    source = setup_source_with_items(client, org)
    target = create_trip(client, org, "Новий похід")
    join_trip(client, member, target["id"], org)

    # учасник цілі, але не джерела
    r = copy_items(client, member, target["id"], source["id"])
    assert r.status_code == 403

    # не учасник цілі взагалі (get_accessible_trip блокує до перевірки джерела)
    r = copy_items(client, outsider, target["id"], source["id"])
    assert r.status_code == 403

    # повне членство — успіх
    join_trip(client, member, source["id"], org)
    assert copy_items(client, member, target["id"], source["id"]).status_code == 200