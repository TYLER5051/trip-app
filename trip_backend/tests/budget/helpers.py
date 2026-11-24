"""Спільні хелпери для тестів бюджету."""
from decimal import Decimal


def dec(value):
    """Нормалізація суми з API ('0' vs '0.00') до Decimal для порівнянь."""
    return Decimal(str(value))


def create_trip(client, headers, title="Похід"):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def join_trip(client, trip_id, who_headers, org_headers):
    token = client.get(f"/trips/{trip_id}/invite", headers=org_headers).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=who_headers)
    assert r.status_code == 200, r.text


def trip_detail(client, trip_id, headers):
    r = client.get(f"/trips/{trip_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def owner_id(client, trip_id, headers):
    return trip_detail(client, trip_id, headers)["owner"]["id"]


def user_id_of(client, trip_id, username, headers):
    d = trip_detail(client, trip_id, headers)
    return next(u["id"] for u in d["participants"] if u["username"] == username)


def add_contribution(client, trip_id, amount, headers, note=None):
    body = {"amount": amount}
    if note is not None:
        body["note"] = note
    r = client.post(f"/trips/{trip_id}/budget/contributions", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def add_expense(client, trip_id, headers, name, amount, shares,
                paid_from_pool=True, paid_by_user_id=None, note=None):
    r = client.post(
        f"/trips/{trip_id}/budget/expenses",
        json={
            "name": name,
            "amount": amount,
            "paid_from_pool": paid_from_pool,
            "paid_by_user_id": paid_by_user_id,
            "shares": shares,
            "note": note,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def budget_list(client, trip_id, headers, **params):
    r = client.get(f"/trips/{trip_id}/budget", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def overview(client, trip_id, headers):
    r = client.get(f"/trips/{trip_id}/budget/overview", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def settlement(client, trip_id, headers):
    r = client.get(f"/trips/{trip_id}/budget/settlement", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
