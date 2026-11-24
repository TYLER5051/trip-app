"""
Тести витрат.

Правила:
  - витрата може бути із спільного банку (paid_from_pool) або особистою;
  - сума часток дорівнює сумі витрати, користувачі у частках унікальні;
  - усі учасники часток і платник мають бути учасниками поїздки;
  - оплата з банку не повинна виснажувати банк (400);
  - редагувати/видаляти витрату може лише її автор або організатор;
  - PATCH зі зміною суми без нових часток заборонений (400).
"""
from tests.budget.helpers import (
    create_trip,
    join_trip,
    owner_id,
    user_id_of,
    add_contribution,
    add_expense,
    budget_list,
    overview,
    dec,
)


def test_create_pool_expense_equal_split(client, auth_headers):
    org = auth_headers("org_e")
    user = auth_headers("user_e")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_e", org)

    add_contribution(client, trip["id"], "100.00", org)
    e = add_expense(client, trip["id"], org, "Обід", "60.00",
                    [{"user_id": oid, "amount": "30.00"}, {"user_id": uid, "amount": "30.00"}])
    assert e["name"] == "Обід"
    assert e["paid_from_pool"] is True
    assert len(e["shares"]) == 2

    assert dec(overview(client, trip["id"], org)["bank_balance"]) == dec("40.00")


def test_create_personal_expense_does_not_touch_bank(client, auth_headers):
    org = auth_headers("org_e")
    user = auth_headers("user_e")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    uid = user_id_of(client, trip["id"], "user_e", org)

    add_contribution(client, trip["id"], "100.00", user)
    e = add_expense(client, trip["id"], user, "Таксі", "25.00",
                    [{"user_id": uid, "amount": "25.00"}],
                    paid_from_pool=False, paid_by_user_id=uid)
    assert e["paid_by_user"]["username"] == "user_e"
    assert dec(overview(client, trip["id"], org)["bank_balance"]) == dec("100.00")


def test_hybrid_split_unequal_shares(client, auth_headers):
    org = auth_headers("org_e")
    user = auth_headers("user_e")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_e", org)

    add_contribution(client, trip["id"], "150.00", org)
    e = add_expense(client, trip["id"], org, "Продукти", "150.00",
                    [{"user_id": oid, "amount": "100.00"}, {"user_id": uid, "amount": "50.00"}])
    amounts = {s["user"]["username"]: dec(s["amount"]) for s in e["shares"]}
    assert amounts == {"org_e": dec("100.00"), "user_e": dec("50.00")}


def test_share_user_must_be_member(client, auth_headers):
    org = auth_headers("org_e")
    outsider = auth_headers("outsider_e")
    trip = create_trip(client, org)
    add_contribution(client, trip["id"], "50.00", org)
    outsider_id = client.get("/users/me", headers=outsider).json()["id"]

    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Чужак",
            "amount": "50.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": outsider_id, "amount": "50.00"}],
        },
        headers=org,
    )
    assert r.status_code == 400


def test_payer_must_be_member(client, auth_headers):
    org = auth_headers("org_e")
    outsider = auth_headers("outsider_e")
    trip = create_trip(client, org)
    oid = owner_id(client, trip["id"], org)
    outsider_id = client.get("/users/me", headers=outsider).json()["id"]

    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Чужий платник",
            "amount": "50.00",
            "paid_from_pool": False,
            "paid_by_user_id": outsider_id,
            "shares": [{"user_id": oid, "amount": "50.00"}],
        },
        headers=org,
    )
    assert r.status_code == 400


def test_duplicate_share_users_rejected(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Дублі",
            "amount": "50.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [
                {"user_id": trip["owner"]["id"], "amount": "25.00"},
                {"user_id": trip["owner"]["id"], "amount": "25.00"},
            ],
        },
        headers=org,
    )
    assert r.status_code == 422


def test_shares_sum_must_equal_amount(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Розбіжність",
            "amount": "100.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": trip["owner"]["id"], "amount": "45.00"}],
        },
        headers=org,
    )
    assert r.status_code == 422


def test_personal_expense_requires_payer(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Без платника",
            "amount": "50.00",
            "paid_from_pool": False,
            "paid_by_user_id": None,
            "shares": [{"user_id": trip["owner"]["id"], "amount": "50.00"}],
        },
        headers=org,
    )
    assert r.status_code == 422


def test_bank_insufficient_400(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    add_contribution(client, trip["id"], "30.00", org)
    oid = owner_id(client, trip["id"], org)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Понад банк",
            "amount": "100.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": oid, "amount": "100.00"}],
        },
        headers=org,
    )
    assert r.status_code == 400


def test_outsider_forbidden_expenses(client, auth_headers):
    org = auth_headers("org_e")
    outsider = auth_headers("outsider_e")
    trip = create_trip(client, org)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "Чуже",
            "amount": "10.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": trip["owner"]["id"], "amount": "10.00"}],
        },
        headers=outsider,
    )
    assert r.status_code == 403


def test_archived_trip_rejects_expense(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    assert client.post(f"/trips/{trip['id']}/archive", headers=org).status_code == 200
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "В архіві",
            "amount": "10.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": trip["owner"]["id"], "amount": "10.00"}],
        },
        headers=org,
    )
    assert r.status_code == 400


def test_name_min_length(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    r = client.post(
        f"/trips/{trip['id']}/budget/expenses",
        json={
            "name": "A",
            "amount": "10.00",
            "paid_from_pool": True,
            "paid_by_user_id": None,
            "shares": [{"user_id": trip["owner"]["id"], "amount": "10.00"}],
        },
        headers=org,
    )
    assert r.status_code == 422


def test_update_only_name_ok(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    add_contribution(client, trip["id"], "50.00", org)
    oid = owner_id(client, trip["id"], org)
    e = add_expense(client, trip["id"], org, "Обід", "50.00", [{"user_id": oid, "amount": "50.00"}])

    r = client.patch(f"/trips/{trip['id']}/budget/expenses/{e['id']}", json={"name": "Вечеря"}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Вечеря"
    assert r.json()["amount"] == "50.00"


def test_update_amount_without_shares_400(client, auth_headers):
    org = auth_headers("org_e")
    user = auth_headers("user_e")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_e", org)

    add_contribution(client, trip["id"], "200.00", org)
    e = add_expense(client, trip["id"], org, "Продукти", "100.00",
                    [{"user_id": oid, "amount": "50.00"}, {"user_id": uid, "amount": "50.00"}])
    # змінювати суму без нових часток не можна (сума часток розходиться)
    r = client.patch(f"/trips/{trip['id']}/budget/expenses/{e['id']}", json={"amount": "120.00"}, headers=org)
    assert r.status_code == 400


def test_full_share_replacement(client, auth_headers):
    org = auth_headers("org_e")
    user = auth_headers("user_e")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_e", org)

    add_contribution(client, trip["id"], "200.00", org)
    e = add_expense(client, trip["id"], org, "Обід", "100.00",
                    [{"user_id": oid, "amount": "50.00"}, {"user_id": uid, "amount": "50.00"}])

    r = client.patch(f"/trips/{trip['id']}/budget/expenses/{e['id']}",
                     json={"shares": [{"user_id": oid, "amount": "100.00"}]}, headers=org)
    assert r.status_code == 200, r.text
    assert len(r.json()["shares"]) == 1
    assert r.json()["shares"][0]["user"]["username"] == "org_e"
    assert r.json()["shares"][0]["amount"] == "100.00"


def test_participant_cannot_update_foreign_expense(client, auth_headers):
    org = auth_headers("org_e")
    user = auth_headers("user_e")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)

    add_contribution(client, trip["id"], "50.00", org)
    e = add_expense(client, trip["id"], org, "Обід", "50.00", [{"user_id": oid, "amount": "50.00"}])

    r = client.patch(f"/trips/{trip['id']}/budget/expenses/{e['id']}", json={"name": "Чужак"}, headers=user)
    assert r.status_code == 403
    r = client.delete(f"/trips/{trip['id']}/budget/expenses/{e['id']}", headers=user)
    assert r.status_code == 403


def test_delete_expense_restores_bank(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    oid = owner_id(client, trip["id"], org)
    add_contribution(client, trip["id"], "50.00", org)
    e = add_expense(client, trip["id"], org, "Обід", "30.00", [{"user_id": oid, "amount": "30.00"}])
    assert dec(overview(client, trip["id"], org)["bank_balance"]) == dec("20.00")

    r = client.delete(f"/trips/{trip['id']}/budget/expenses/{e['id']}", headers=org)
    assert r.status_code == 200, r.text
    assert budget_list(client, trip["id"], org)["total"] == 1  # лишився внесок
    assert dec(overview(client, trip["id"], org)["bank_balance"]) == dec("50.00")


def test_expense_logged_to_activity(client, auth_headers):
    org = auth_headers("org_e")
    trip = create_trip(client, org)
    oid = owner_id(client, trip["id"], org)
    add_contribution(client, trip["id"], "50.00", org)
    e = add_expense(client, trip["id"], org, "Обід", "50.00", [{"user_id": oid, "amount": "50.00"}])

    feed = client.get("/users/me/activities", headers=org).json()["items"]
    assert any(a["action"] == "expense_added" and a["details"]["expense_id"] == e["id"] for a in feed)

    r = client.delete(f"/trips/{trip['id']}/budget/expenses/{e['id']}", headers=org)
    assert r.status_code == 200, r.text
    feed = client.get("/users/me/activities", headers=org).json()["items"]
    assert any(a["action"] == "expense_deleted" for a in feed)
