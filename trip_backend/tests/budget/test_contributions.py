"""
Тести внесків у спільний банк.

Правила:
  - внесок може створювати будь-який учасник активної поїздки (не архівованої);
  - amount обов'язково > 0, note ≤ 200 символів;
  - редагувати/видаляти внесок може лише його автор або організатор;
  - банк не повинен піти в мінус: зменшення/видалення внеску, що виснажує банк, заборонене.
"""
from decimal import Decimal
from tests.budget.helpers import (
    create_trip,
    join_trip,
    owner_id,
    add_contribution,
    budget_list,
    overview,
    dec,
)


def test_create_contribution_basic(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)

    c = add_contribution(client, trip["id"], "100.00", org, note="перший внесок")
    assert c["amount"] == "100.00"
    assert c["note"] == "перший внесок"
    assert c["user"]["username"] == "org_c"

    data = budget_list(client, trip["id"], org)
    assert data["total"] == 1
    assert data["contributions"][0]["amount"] == "100.00"

    ov = overview(client, trip["id"], org)
    assert dec(ov["bank_balance"]) == Decimal("100.00")
    assert dec(ov["total_contributions"]) == Decimal("100.00")


def test_amount_must_be_positive(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    for bad in ("0.00", "-5.00"):
        r = client.post(f"/trips/{trip['id']}/budget/contributions", json={"amount": bad}, headers=org)
        assert r.status_code == 422, (bad, r.text)


def test_note_too_long_rejected(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    r = client.post(
        f"/trips/{trip['id']}/budget/contributions",
        json={"amount": "10.00", "note": "а" * 201},
        headers=org,
    )
    assert r.status_code == 422


def test_outsider_forbidden(client, auth_headers):
    org = auth_headers("org_c")
    outsider = auth_headers("outsider_c")
    trip = create_trip(client, org)

    r = client.get(f"/trips/{trip['id']}/budget", headers=outsider)
    assert r.status_code == 403
    r = client.post(f"/trips/{trip['id']}/budget/contributions", json={"amount": "10.00"}, headers=outsider)
    assert r.status_code == 403


def test_archived_trip_rejects_mutations(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    r = client.post(f"/trips/{trip['id']}/archive", headers=org)
    assert r.status_code == 200, r.text

    r = client.post(f"/trips/{trip['id']}/budget/contributions", json={"amount": "10.00"}, headers=org)
    assert r.status_code == 400
    # читання з архіву доступне
    r = client.get(f"/trips/{trip['id']}/budget", headers=org)
    assert r.status_code == 200


def test_update_own_contribution(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    c = add_contribution(client, trip["id"], "50.00", org)

    r = client.patch(f"/trips/{trip['id']}/budget/contributions/{c['id']}", json={"amount": "80.00"}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "80.00"
    assert dec(overview(client, trip["id"], org)["bank_balance"]) == Decimal("80.00")


def test_participant_cannot_update_foreign_contribution(client, auth_headers):
    org = auth_headers("org_c")
    user = auth_headers("user_c")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    c = add_contribution(client, trip["id"], "50.00", user)
    r = client.patch(f"/trips/{trip['id']}/budget/contributions/{c['id']}", json={"amount": "1.00"}, headers=org)
    assert r.status_code == 200, r.text  # організатор може редагувати чужий внесок

    c2 = add_contribution(client, trip["id"], "60.00", org)
    r = client.patch(f"/trips/{trip['id']}/budget/contributions/{c2['id']}", json={"amount": "1.00"}, headers=user)
    assert r.status_code == 403


def test_participant_cannot_delete_foreign_contribution(client, auth_headers):
    org = auth_headers("org_c")
    user = auth_headers("user_c")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    c = add_contribution(client, trip["id"], "50.00", org)
    r = client.delete(f"/trips/{trip['id']}/budget/contributions/{c['id']}", headers=user)
    assert r.status_code == 403


def test_delete_own_contribution(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    c = add_contribution(client, trip["id"], "50.00", org)

    r = client.delete(f"/trips/{trip['id']}/budget/contributions/{c['id']}", headers=org)
    assert r.status_code == 200, r.text
    assert budget_list(client, trip["id"], org)["total"] == 0
    assert dec(overview(client, trip["id"], org)["bank_balance"]) == Decimal("0")


def test_delete_contribution_cannot_overdraw_bank(client, auth_headers):
    org = auth_headers("org_c")
    user = auth_headers("user_c")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)

    add_contribution(client, trip["id"], "100.00", user)  # єдині гроші в банку
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Повний банк",
            "amount": "100.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": oid, "amount": "100.00"}],
        },
        headers=org,
    )
    assert r.status_code == 200, r.text

    c = budget_list(client, trip["id"], org)["contributions"][0]
    # видалення внеску виснажило б банк у мінус
    r = client.delete(f"/trips/{trip['id']}/budget/contributions/{c['id']}", headers=user)
    assert r.status_code == 400


def test_update_contribution_cannot_overdraw_bank(client, auth_headers):
    org = auth_headers("org_c")
    user = auth_headers("user_c")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)

    c = add_contribution(client, trip["id"], "100.00", user)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Повний банк",
            "amount": "100.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": oid, "amount": "100.00"}],
        },
        headers=org,
    )
    assert r.status_code == 200, r.text

    r = client.patch(f"/trips/{trip['id']}/budget/contributions/{c['id']}", json={"amount": "50.00"}, headers=user)
    assert r.status_code == 400


def test_update_contribution_requires_amount(client, auth_headers):
    # amount у ContributionUpdate обов'язковий (без default), тож пустий PATCH → 422
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    c = add_contribution(client, trip["id"], "50.00", org)
    r = client.patch(f"/trips/{trip['id']}/budget/contributions/{c['id']}", json={}, headers=org)
    assert r.status_code == 422


def test_budget_list_pagination_newest_first(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    add_contribution(client, trip["id"], "10.00", org)
    add_contribution(client, trip["id"], "20.00", org)

    data = budget_list(client, trip["id"], org, limit=1, offset=0)
    assert data["total"] == 2
    assert len(data["contributions"]) == 1
    assert data["contributions"][0]["amount"] == "20.00"  # найновіший першим

    data = budget_list(client, trip["id"], org, limit=1, offset=1)
    assert data["contributions"][0]["amount"] == "10.00"


def test_contribution_logged_to_activity(client, auth_headers):
    org = auth_headers("org_c")
    trip = create_trip(client, org)
    c = add_contribution(client, trip["id"], "42.00", org)

    feed = client.get("/users/me/activities", headers=org).json()["items"]
    act = next(a for a in feed if a["action"] == "contribution_added")
    assert act["trip_id"] == trip["id"]
    assert act["details"]["amount"] == "42.00"
    assert act["details"]["contribution_id"] == c["id"]

    r = client.delete(f"/trips/{trip['id']}/budget/contributions/{c['id']}", headers=org)
    assert r.status_code == 200, r.text
    feed = client.get("/users/me/activities", headers=org).json()["items"]
    assert any(a["action"] == "contribution_deleted" for a in feed)
