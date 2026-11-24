"""
Тести видалення акаунта з фінансовими записами.

Правила:
  - видалення акаунта НЕ видаляє фінзаписи: user_id у внесках/частках і
    paid_by_user_id/created_by_id у витратах стають NULL;
  - записи, створені живим користувачем, не чіпаються;
  - видалення організатора прибирає його поїздки разом з бюджетом.
"""
import json

from tests.budget.helpers import (
    create_trip,
    join_trip,
    owner_id,
    user_id_of,
    add_contribution,
    add_expense,
    budget_list,
    overview,
    settlement,
    trip_detail,
    dec,
)


def delete_account(client, headers, password="password123"):
    return client.request(
        "DELETE", "/users/me",
        content=json.dumps({"current_password": password}),
        headers={**headers, "Content-Type": "application/json"},
    )


def test_delete_account_nullifies_contribution(client, auth_headers):
    org = auth_headers("org_d")
    user = auth_headers("user_d")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    add_contribution(client, trip["id"], "100.00", user)
    assert delete_account(client, user).status_code == 200

    data = budget_list(client, trip["id"], org)
    assert data["total"] == 1  # лише внесок, рядок збережено
    contribs = data["contributions"]
    assert len(contribs) == 1
    assert contribs[0]["user"] is None

    ov = overview(client, trip["id"], org)
    assert dec(ov["deleted_users"]["contributed"]) == dec("100.00")
    assert dec(ov["bank_balance"]) == dec("100.00")
    # видаленого учасника немає серед живих
    assert not any(u["username"] == "user_d" for u in trip_detail(client, trip["id"], org)["participants"])


def test_delete_account_nullifies_payer_and_shares(client, auth_headers):
    org = auth_headers("org_d")
    user = auth_headers("user_d")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_d", org)

    add_contribution(client, trip["id"], "300.00", org)
    add_expense(client, trip["id"], user, "Особисте", "50.00",
                [{"user_id": uid, "amount": "50.00"}],
                paid_from_pool=False, paid_by_user_id=uid)
    add_expense(client, trip["id"], org, "Спільна", "150.00",
                [{"user_id": oid, "amount": "75.00"}, {"user_id": uid, "amount": "75.00"}])

    assert delete_account(client, user).status_code == 200

    expenses = {e["name"]: e for e in budget_list(client, trip["id"], org)["expenses"]}
    assert expenses["Особисте"]["paid_by_user"] is None
    assert expenses["Особисте"]["created_by"] is None
    assert expenses["Особисте"]["shares"][0]["user"] is None
    # живий організатор не зачеплений
    assert expenses["Спільна"]["created_by"]["username"] == "org_d"
    share_users = {s["user"]["username"] if s["user"] else None for s in expenses["Спільна"]["shares"]}
    assert share_users == {"org_d", None}

    ov = overview(client, trip["id"], org)
    assert dec(ov["deleted_users"]["share_costs"]) == dec("125.00")  # 50 + 75
    assert dec(ov["deleted_users"]["net"]) == dec("-75.00")          # paid_by_self 50 - share_costs 125


def test_delete_account_wrong_password_untouched(client, auth_headers):
    org = auth_headers("org_d")
    user = auth_headers("user_d")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    add_contribution(client, trip["id"], "100.00", user)
    assert delete_account(client, user, password="wrong").status_code == 400

    c = budget_list(client, trip["id"], org)["contributions"][0]
    assert c["user"]["username"] == "user_d"
    assert client.get("/users/me", headers=user).status_code == 200


def test_delete_account_keeps_live_org_finances(client, auth_headers):
    org = auth_headers("org_d")
    user = auth_headers("user_d")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)

    add_contribution(client, trip["id"], "100.00", org)
    add_contribution(client, trip["id"], "100.00", user)
    add_expense(client, trip["id"], org, "Обід", "50.00",
                [{"user_id": oid, "amount": "50.00"}])

    assert delete_account(client, user).status_code == 200

    # банк 150 (200 внесків - 50 з банку), живий net=50, deleted вклад 100 → залишок 100 у банку
    st = settlement(client, trip["id"], org)
    assert dec(st["bank_balance"]) == dec("150.00")
    assert st["deleted_users_note"] is not None
    assert "100" in st["deleted_users_note"]
    payouts = [{"user": p["user"]["username"], "amount": dec(p["amount"])} for p in st["bank_payouts"]]
    assert payouts == [{"user": "org_d", "amount": dec("50.00")}]


def test_delete_owner_cascades_budget(client, auth_headers):
    org = auth_headers("org_d")
    user = auth_headers("user_d")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)

    add_contribution(client, trip["id"], "200.00", org)
    add_expense(client, trip["id"], org, "Обід", "50.00",
                [{"user_id": oid, "amount": "50.00"}])

    assert delete_account(client, org).status_code == 200

    r = client.get(f"/trips/{trip['id']}/budget", headers=user)
    assert r.status_code == 404
    # поїздка зникла і для самого колись організатора
    r = client.get("/trips/", headers=user)
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_edit_expense_with_deleted_user_share_blocked(client, auth_headers):
    org = auth_headers("org_d")
    user = auth_headers("user_d")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    uid = user_id_of(client, trip["id"], "user_d", org)

    add_contribution(client, trip["id"], "300.00", org)
    add_expense(client, trip["id"], user, "Особисте", "50.00",
                [{"user_id": uid, "amount": "50.00"}],
                paid_from_pool=False, paid_by_user_id=uid)

    assert delete_account(client, user).status_code == 200

    e = budget_list(client, trip["id"], org)["expenses"][0]
    assert e["shares"][0]["user"] is None  # платник і частка видалені

    # редагування витрати з часткою/платником видаленого користувача заборонене (400)
    r = client.patch(f"/trips/{trip['id']}/budget/expenses/{e['id']}", json={"name": "Нове"}, headers=org)
    assert r.status_code == 400
    assert "видалених" in r.json()["detail"]

    # видалення такої витрати — дозволено
    r = client.delete(f"/trips/{trip['id']}/budget/expenses/{e['id']}", headers=org)
    assert r.status_code == 200
