"""
Тести блокування видалення учасника з фінансовими записами.

Правила:
  - remove_participant / leave повертають 409, якщо в учасника є фінзаписи в поїздці:
    внески, витрати (платником або автором) або частки;
  - без таких записів removal/leave працюють як раніше (200).
"""
from tests.budget.helpers import (
    create_trip,
    join_trip,
    owner_id,
    user_id_of,
    add_contribution,
    add_expense,
    trip_detail,
)


def test_remove_blocked_when_user_contributed(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    add_contribution(client, trip["id"], "100.00", user)
    uid = user_id_of(client, trip["id"], "user_p", org)

    r = client.delete(f"/trips/{trip['id']}/participants/{uid}", headers=org)
    assert r.status_code == 409, r.text
    assert any(u["username"] == "user_p" for u in trip_detail(client, trip["id"], org)["participants"])


def test_leave_blocked_when_user_contributed(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    add_contribution(client, trip["id"], "100.00", user)
    r = client.delete(f"/trips/{trip['id']}/leave", headers=user)
    assert r.status_code == 409, r.text


def test_remove_blocked_when_user_paid_personal_expense(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    uid = user_id_of(client, trip["id"], "user_p", org)

    add_expense(client, trip["id"], user, "Таксі", "50.00",
                [{"user_id": uid, "amount": "50.00"}],
                paid_from_pool=False, paid_by_user_id=uid)

    r = client.delete(f"/trips/{trip['id']}/participants/{uid}", headers=org)
    assert r.status_code == 409, r.text
    r = client.delete(f"/trips/{trip['id']}/leave", headers=user)
    assert r.status_code == 409, r.text


def test_remove_blocked_when_share_only(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_p", org)

    # сам юзер нічого не створював — лише фігурує у частці чужої витрати
    add_contribution(client, trip["id"], "200.00", org)
    add_expense(client, trip["id"], org, "Обід", "200.00",
                [{"user_id": oid, "amount": "100.00"}, {"user_id": uid, "amount": "100.00"}])

    r = client.delete(f"/trips/{trip['id']}/participants/{uid}", headers=org)
    assert r.status_code == 409, r.text
    r = client.delete(f"/trips/{trip['id']}/leave", headers=user)
    assert r.status_code == 409, r.text


def test_remove_blocked_when_user_created_pool_expense(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    oid = owner_id(client, trip["id"], org)
    uid = user_id_of(client, trip["id"], "user_p", org)

    add_contribution(client, trip["id"], "200.00", org)
    # автор витрати — user (платник None, оплата з банку)
    add_expense(client, trip["id"], user, "Продукти", "100.00",
                [{"user_id": oid, "amount": "50.00"}, {"user_id": uid, "amount": "50.00"}])

    r = client.delete(f"/trips/{trip['id']}/participants/{uid}", headers=org)
    assert r.status_code == 409, r.text


def test_remove_ok_after_finances_cleared(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    uid = user_id_of(client, trip["id"], "user_p", org)

    c = add_contribution(client, trip["id"], "100.00", user)
    assert client.delete(f"/trips/{trip['id']}/budget/contributions/{c['id']}", headers=org).status_code == 200

    r = client.delete(f"/trips/{trip['id']}/participants/{uid}", headers=org)
    assert r.status_code == 200, r.text


def test_remove_ok_without_budget_records(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    uid = user_id_of(client, trip["id"], "user_p", org)

    r = client.delete(f"/trips/{trip['id']}/participants/{uid}", headers=org)
    assert r.status_code == 200, r.text
    assert not any(u["username"] == "user_p" for u in trip_detail(client, trip["id"], org)["participants"])


def test_leave_ok_without_budget_records(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)

    r = client.delete(f"/trips/{trip['id']}/leave", headers=user)
    assert r.status_code == 200, r.text
    assert not any(u["username"] == "user_p" for u in trip_detail(client, trip["id"], org)["participants"])


def test_leave_archived_trip_without_finances_allowed(client, auth_headers):
    org = auth_headers("org_p")
    user = auth_headers("user_p")
    trip = create_trip(client, org)
    join_trip(client, trip["id"], user, org)
    assert client.post(f"/trips/{trip['id']}/archive", headers=org).status_code == 200

    r = client.delete(f"/trips/{trip['id']}/leave", headers=user)
    assert r.status_code == 200, r.text
