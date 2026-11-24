"""
Тести балансів учасників та розрахунків.

Формули:
  - bank = внески - оплати з банку;
  - net учасника = contributed + paid_by_self - share_costs;
  - settlement: гроші з банку йдуть кредиторам пропорційно net (r = min(1, bank/sum_pos)),
    борги перекриваються переказами «боржник -> кредитор» (greedy).
"""
from tests.budget.helpers import (
    create_trip,
    join_trip,
    owner_id,
    user_id_of,
    add_contribution,
    add_expense,
    overview,
    settlement,
    dec,
)


def test_overview_empty_trip(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    ov = overview(client, trip["id"], org)
    assert dec(ov["bank_balance"]) == dec("0")
    assert dec(ov["total_contributions"]) == dec("0")
    assert dec(ov["total_expenses"]) == dec("0")
    usernames = {p["user"]["username"] for p in ov["participants"]}
    assert usernames == {"org_b", "user_b"}
    assert all(dec(p["net"]) == dec("0") for p in ov["participants"])


def test_overview_pool_split_nets(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_b", org)

    add_contribution(client, trip["id"], "100.00", org)
    add_contribution(client, trip["id"], "100.00", user)
    add_expense(client, trip["id"], org, "Обід", "60.00",
                [{"user_id": oid, "amount": "30.00"}, {"user_id": uid, "amount": "30.00"}])

    ov = overview(client, trip["id"], org)
    assert dec(ov["bank_balance"]) == dec("140.00")
    assert dec(ov["total_contributions"]) == dec("200.00")
    assert dec(ov["total_expenses"]) == dec("60.00")
    nets = {p["user"]["username"]: dec(p["net"]) for p in ov["participants"]}
    assert nets == {"org_b": dec("70.00"), "user_b": dec("70.00")}


def test_overview_personal_expense(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_b", org)

    add_contribution(client, trip["id"], "100.00", org)
    add_contribution(client, trip["id"], "100.00", user)
    add_expense(client, trip["id"], org, "Таксі за всіх", "20.00",
                [{"user_id": uid, "amount": "20.00"}],
                paid_from_pool=False, paid_by_user_id=oid)

    ov = overview(client, trip["id"], org)
    nets = {p["user"]["username"]: dec(p["net"]) for p in ov["participants"]}
    assert nets == {"org_b": dec("120.00"), "user_b": dec("80.00")}
    # особиста оплата не чіпає банк
    assert dec(ov["bank_balance"]) == dec("200.00")


def test_settlement_empty_trip(client, auth_headers):
    org = auth_headers("org_b")
    trip = create_trip(client, org)

    st = settlement(client, trip["id"], org)
    assert dec(st["bank_balance"]) == dec("0")
    assert st["transfers"] == []
    assert st["bank_payouts"] == []
    assert st["deleted_users_note"] is None


def test_settlement_bank_pays_creditors(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_b", org)

    add_contribution(client, trip["id"], "100.00", org)
    add_contribution(client, trip["id"], "100.00", user)
    add_expense(client, trip["id"], org, "Обід", "60.00",
                [{"user_id": oid, "amount": "30.00"}, {"user_id": uid, "amount": "30.00"}])

    st = settlement(client, trip["id"], org)
    assert st["transfers"] == []
    payouts = {p["user"]["username"]: dec(p["amount"]) for p in st["bank_payouts"]}
    assert payouts == {"org_b": dec("70.00"), "user_b": dec("70.00")}
    assert dec(st["bank_balance"]) == dec("140.00")


def test_settlement_individual_debts_without_bank(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_b", org)

    # банк порожній, орг оплатив 50 особисто: 30 на себе, 20 за іншого
    add_expense(client, trip["id"], org, "Таксі", "50.00",
                [{"user_id": oid, "amount": "30.00"}, {"user_id": uid, "amount": "20.00"}],
                paid_from_pool=False, paid_by_user_id=oid)

    st = settlement(client, trip["id"], org)
    assert st["bank_payouts"] == []
    got = [{"from": t["from_user"]["username"], "to": t["to_user"]["username"], "amount": dec(t["amount"])}
           for t in st["transfers"]]
    assert got == [{"from": "user_b", "to": "org_b", "amount": dec("20.00")}]


def test_settlement_partial_bank_coverage(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_b", org)

    add_contribution(client, trip["id"], "100.00", org)
    add_contribution(client, trip["id"], "100.00", user)
    # орг оплатив 300 особисто; банк = 200 < sum_pos = 250 → часткове покриття
    add_expense(client, trip["id"], org, "Оренда", "300.00",
                [{"user_id": oid, "amount": "150.00"}, {"user_id": uid, "amount": "150.00"}],
                paid_from_pool=False, paid_by_user_id=oid)

    st = settlement(client, trip["id"], org)
    assert dec(st["bank_balance"]) == dec("200.00")
    payouts = [{"user": p["user"]["username"], "amount": dec(p["amount"])} for p in st["bank_payouts"]]
    assert payouts == [{"user": "org_b", "amount": dec("200.00")}]
    got = [{"from": t["from_user"]["username"], "to": t["to_user"]["username"], "amount": dec(t["amount"])}
           for t in st["transfers"]]
    assert got == [{"from": "user_b", "to": "org_b", "amount": dec("50.00")}]


def test_bank_balance_formula(client, auth_headers):
    org = auth_headers("org_b")
    user = auth_headers("user_b")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_b", org)

    add_contribution(client, trip["id"], "150.00", org)
    add_contribution(client, trip["id"], "50.00", user)
    add_expense(client, trip["id"], org, "Обід", "70.00",
                [{"user_id": oid, "amount": "35.00"}, {"user_id": uid, "amount": "35.00"}])
    add_expense(client, trip["id"], user, "Особисте", "10.00",
                [{"user_id": uid, "amount": "10.00"}],
                paid_from_pool=False, paid_by_user_id=uid)

    ov = overview(client, trip["id"], org)
    # банк = 150 + 50 - 70 = 130 (особисті оплати банк не чіпають)
    assert dec(ov["bank_balance"]) == dec("130.00")
