"""
Тести дій з учасниками після рефакторингу на bulk-операції.

  - leave: учасник виходить, його взяті речі стають вільними;
  - remove_participant: організатор видаляє учасника, речі звільняються;
  - після видалення учасник не рахується в деталях поїздки.
"""


def create_trip(client, headers):
    r = client.post("/trips/", json={"title": "Похід"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def invite_token_of(client, trip_id, headers):
    r = client.get(f"/trips/{trip_id}/invite", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["invite_token"]


def make_category(client, headers, trip_id, name="Спорядження"):
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def make_item(client, headers, trip_id, cat_id, name):
    r = client.post(
        "/items/",
        json={"trip_id": trip_id, "category_id": cat_id, "name": name},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def join_trip(client, trip_id, token, who_headers):
    r = client.post(f"/trips/invite/{token}", headers=who_headers)
    assert r.status_code == 200, r.text


def test_leave_frees_assigned_items(client, auth_headers):
    org = auth_headers("org")
    user = auth_headers("user_x")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)
    join_trip(client, trip["id"], token, user)

    cat = make_category(client, org, trip["id"])
    item = make_item(client, org, trip["id"], cat["id"], "Намет")

    r = client.post(f"/items/{item['id']}/assign", headers=user)
    assert r.status_code == 200, r.text

    r = client.delete(f"/trips/{trip['id']}/leave", headers=user)
    assert r.status_code == 200, r.text

    trip_detail = client.get(f"/trips/{trip['id']}", headers=org).json()
    assert not any(u["username"] == "user_x" for u in trip_detail["participants"])
    free_item = next(i for i in trip_detail["items"] if i["id"] == item["id"])
    assert free_item["assigned_users"] == []


def test_remove_participant_frees_items(client, auth_headers):
    org = auth_headers("org")
    user = auth_headers("user_y")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)
    join_trip(client, trip["id"], token, user)

    cat = make_category(client, org, trip["id"])
    item = make_item(client, org, trip["id"], cat["id"], "Палатка")
    assert client.post(f"/items/{item['id']}/assign", headers=user).status_code == 200

    trip_detail = client.get(f"/trips/{trip['id']}", headers=org).json()
    user_id = trip_detail["participants"][0]["id"]
    r = client.delete(f"/trips/{trip['id']}/participants/{user_id}", headers=org)
    assert r.status_code == 200, r.text

    trip_detail = client.get(f"/trips/{trip['id']}", headers=org).json()
    assert not any(u["username"] == "user_y" for u in trip_detail["participants"])
    free_item = next(i for i in trip_detail["items"] if i["id"] == item["id"])
    assert free_item["assigned_users"] == []


def test_non_participant_cannot_leave(client, auth_headers):
    org = auth_headers("org")
    outsider = auth_headers("outsider")
    trip = create_trip(client, org)

    r = client.delete(f"/trips/{trip['id']}/leave", headers=outsider)
    assert r.status_code == 400