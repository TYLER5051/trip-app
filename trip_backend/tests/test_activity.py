"""
Тести Фічі 9: стрічка активності (Activity).
"""
import json


def make_trip(client, headers, title):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def make_category(client, headers, trip_id, name):
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def make_item(client, headers, trip_id, category_id, name, quantity=1):
    r = client.post(
        "/items/",
        json={"name": name, "trip_id": trip_id, "category_id": category_id, "quantity": quantity},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def join_trip(client, headers, trip_id, inviter_headers):
    token = client.get(f"/trips/{trip_id}/invite", headers=inviter_headers).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=headers)
    assert r.status_code == 200, r.text


def feed(client, headers, params=None):
    r = client.get("/users/me/activities", params=params or {}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_trip_created_is_logged(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід у Карпати")

    items = feed(client, org)["items"]
    assert len(items) == 1
    act = items[0]
    assert act["action"] == "trip_created"
    assert act["trip_id"] == trip["id"]
    assert act["trip"]["title"] == "Похід у Карпати"
    assert act["actor"]["username"] == "org_feed"
    assert act["details"] == {"title": "Похід у Карпати"}


def test_item_created_logged_with_parsed_details(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    cat = make_category(client, org, trip["id"], "Спорядження")
    make_item(client, org, trip["id"], cat["id"], "Намет")

    act = feed(client, org)["items"][0]
    assert act["action"] == "item_created"
    assert isinstance(act["details"], dict)
    assert act["details"]["name"] == "Намет"
    assert act["item_id"] is not None
    assert act["category_id"] == cat["id"]


def test_assign_and_unassign_logged(client, auth_headers):
    org = auth_headers("org_feed")
    u1 = auth_headers("part_feed")
    trip = make_trip(client, org, "Похід")
    join_trip(client, u1, trip["id"], org)
    cat = make_category(client, org, trip["id"], "Спорядження")
    item = make_item(client, org, trip["id"], cat["id"], "Намет", quantity=2)

    r = client.post(f"/items/{item['id']}/assign", json={"quantity": 2}, headers=u1)
    assert r.status_code == 200, r.text

    acts = feed(client, u1)["items"]
    assign_act = next(a for a in acts if a["action"] == "item_assigned")
    assert assign_act["actor"]["username"] == "part_feed"
    assert assign_act["details"]["quantity"] == 2
    assert assign_act["details"]["name"] == "Намет"

    r = client.delete(f"/items/{item['id']}/assign", headers=u1)
    assert r.status_code == 200, r.text

    acts = feed(client, u1)["items"]
    unassign_act = next(a for a in acts if a["action"] == "item_unassigned")
    assert unassign_act["details"]["name"] == "Намет"


def test_item_moved_logged(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    cat_a = make_category(client, org, trip["id"], "Спорядження")
    cat_b = make_category(client, org, trip["id"], "Харчі")
    item = make_item(client, org, trip["id"], cat_a["id"], "Намет")

    r = client.patch(f"/items/{item['id']}", json={"category_id": cat_b["id"]}, headers=org)
    assert r.status_code == 200, r.text

    r = client.patch(f"/items/{item['id']}", json={"category_id": None}, headers=org)
    assert r.status_code == 200, r.text

    moved = [a for a in feed(client, org)["items"] if a["action"] == "item_moved"]
    assert len(moved) == 2

    details = [a["details"] for a in moved]
    assert {"name": "Намет", "from": "Спорядження", "to": "Харчі"} in details
    assert {"name": "Намет", "from": "Харчі", "to": "Інше"} in details

    # стрічка найновішою дією першою (created_at DESC, id DESC)
    assert moved[0]["details"] == {"name": "Намет", "from": "Харчі", "to": "Інше"}
    assert moved[0]["category_id"] is None
    assert moved[1]["category_id"] == cat_b["id"]


def test_item_deleted_logged_with_snapshot(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    cat = make_category(client, org, trip["id"], "Спорядження")
    item = make_item(client, org, trip["id"], cat["id"], "Старий примус")

    r = client.delete(f"/items/{item['id']}", headers=org)
    assert r.status_code == 200, r.text

    del_act = next(a for a in feed(client, org)["items"] if a["action"] == "item_deleted")
    assert del_act["details"]["name"] == "Старий примус"
    assert del_act["item_id"] is None


def test_category_deleted_logged(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    cat = make_category(client, org, trip["id"], "Мотлох")
    make_item(client, org, trip["id"], cat["id"], "Старий примус")

    r = client.delete(f"/trips/{trip['id']}/categories/{cat['id']}", headers=org)
    assert r.status_code == 200, r.text

    cat_act = next(a for a in feed(client, org)["items"] if a["action"] == "category_deleted")
    assert cat_act["details"]["name"] == "Мотлох"
    assert cat_act["details"]["items_moved"] == 1


def test_participant_joined_logged(client, auth_headers):
    org = auth_headers("org_feed")
    u1 = auth_headers("part_feed")
    trip = make_trip(client, org, "Похід")
    join_trip(client, u1, trip["id"], org)

    joined = next(a for a in feed(client, org)["items"] if a["action"] == "participant_joined")
    assert joined["actor"]["username"] == "part_feed"
    assert joined["trip_id"] == trip["id"]


def test_trip_feed_requires_membership(client, auth_headers):
    org = auth_headers("org_feed")
    outsider = auth_headers("outsider_feed")
    trip = make_trip(client, org, "Приватна поїздка")

    r = client.get(f"/trips/{trip['id']}/activities", headers=outsider)
    assert r.status_code == 403

    r = client.get(f"/trips/{trip['id']}/activities", headers=org)
    assert r.status_code == 200
    assert r.json()["items"][0]["action"] == "trip_created"
    assert r.json()["items"][0]["trip_id"] == trip["id"]


def test_feed_orders_newest_first(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    cat = make_category(client, org, trip["id"], "Спорядження")
    make_item(client, org, trip["id"], cat["id"], "Намет")

    acts = feed(client, org)["items"]
    assert [a["action"] for a in acts] == ["item_created", "trip_created"]
    assert acts[0]["id"] > acts[1]["id"]


def test_profile_feed_filters_foreign_trips(client, auth_headers):
    user_a = auth_headers("user_a")
    user_b = auth_headers("user_b")
    trip_a = make_trip(client, user_a, "Поїздка A")
    make_trip(client, user_b, "Поїздка B")

    acts_a = feed(client, user_a)["items"]
    assert len(acts_a) == 1
    assert acts_a[0]["trip_id"] == trip_a["id"]

    acts_b = feed(client, user_b)["items"]
    assert len(acts_b) == 1
    assert acts_b[0]["trip"]["title"] == "Поїздка B"

    join_trip(client, user_b, trip_a["id"], user_a)

    acts_a = feed(client, user_a)["items"]
    assert [a["action"] for a in acts_a] == ["participant_joined", "trip_created"]
    assert all(a["trip_id"] == trip_a["id"] for a in acts_a)


def test_pagination_limit_offset(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    cat = make_category(client, org, trip["id"], "Спорядження")
    make_item(client, org, trip["id"], cat["id"], "Намет")
    make_item(client, org, trip["id"], cat["id"], "Каремат")

    data = feed(client, org, {"limit": 2, "offset": 0})
    assert data["total"] == 3
    assert len(data["items"]) == 2

    data = feed(client, org, {"limit": 2, "offset": 2})
    assert len(data["items"]) == 1
    assert data["items"][0]["action"] == "trip_created"


def test_trip_deletion_cascades_activities(client, auth_headers):
    org = auth_headers("org_feed")
    trip = make_trip(client, org, "Похід")
    assert len(feed(client, org)["items"]) == 1

    r = client.delete(f"/trips/{trip['id']}", headers=org)
    assert r.status_code == 200, r.text

    assert len(feed(client, org)["items"]) == 0
    r = client.get(f"/trips/{trip['id']}/activities", headers=org)
    assert r.status_code == 404


def test_delete_account_nullifies_actor(client, auth_headers):
    org = auth_headers("org_feed")
    u1 = auth_headers("part_feed")
    trip = make_trip(client, u1, "Поїздка учасника")
    join_trip(client, org, trip["id"], u1)

    org_id = client.get("/users/me", headers=org).json()["id"]
    r = client.request(
        "DELETE",
        "/users/me",
        content=json.dumps({"current_password": "password123"}),
        headers={**org, "Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text

    joined = next(a for a in feed(client, u1)["items"] if a["action"] == "participant_joined")
    assert joined["actor"] is None
    assert joined["details"] == {"username": "org_feed"}
    assert all(a["actor"] is None or a["actor"]["id"] != org_id for a in feed(client, u1)["items"])
