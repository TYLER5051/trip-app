"""
Сліпі зони попереднього набору тестів:
  - /healthz та CORS-заголовки;
  - rate-limit (429) на /register і read-ендпоінти (лімітер вимкнено в conftest);
  - error-шлях delete_item (IntegrityError має давати 409, а не 500);
  - конкурентний assign останнього слота (має бути рівно один переможець) та
    конкурентний join по інвайту (токен багаторазовий — одночасно можуть
    приєднатися всі охочі).
"""

import threading

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import main


def setup_trip(client, auth_headers):
    org = auth_headers("org_hard")
    u1 = auth_headers("hard_one")
    u2 = auth_headers("hard_two")

    trip_id = client.post("/trips/", json={"title": "Похід"}, headers=org).json()["id"]
    cat1 = client.post(f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=org).json()
    cat2 = client.post(f"/trips/{trip_id}/categories/", json={"name": "Харчі"}, headers=org).json()

    invite_token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    for headers in (u1, u2):
        r = client.post(f"/trips/invite/{invite_token}", headers=headers)
        assert r.status_code == 200, r.text

    return trip_id, cat1["id"], cat2["id"], org, u1, u2


def create_item(client, headers, trip_id, category_id, name, **extra):
    body = {"name": name, "trip_id": trip_id, "category_id": category_id, **extra}
    r = client.post("/items/", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# /healthz + CORS
# ---------------------------------------------------------------------------

def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_cors_allowed_origin_reflected(client):
    r = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_unknown_origin_not_reflected(client):
    r = client.get("/healthz", headers={"Origin": "http://evil.example"})
    assert r.headers.get("access-control-allow-origin") is None


# ---------------------------------------------------------------------------
# Rate limiting (429)
# ---------------------------------------------------------------------------

def _enable_limiter():
    previous = main.app.state.limiter.enabled
    main.app.state.limiter.enabled = True
    return previous


def test_register_rate_limited_after_5(client):
    previous = _enable_limiter()
    try:
        for i in range(5):
            r = client.post("/register", json={"username": f"rl_{i}", "password": "password123"})
            assert r.status_code == 200, r.text
        r = client.post("/register", json={"username": "rl_last", "password": "password123"})
        assert r.status_code == 429
    finally:
        main.app.state.limiter.enabled = previous


def test_read_endpoint_rate_limited(client, auth_headers):
    headers = auth_headers("rl_reader")
    previous = _enable_limiter()
    try:
        for _ in range(100):
            r = client.get("/trips/", headers=headers)
            assert r.status_code == 200, r.text
        r = client.get("/trips/", headers=headers)
        assert r.status_code == 429
    finally:
        main.app.state.limiter.enabled = previous


# ---------------------------------------------------------------------------
# delete_item: IntegrityError має давати 409, а не 500 (регресія status=)
# ---------------------------------------------------------------------------

def test_delete_item_integrity_error_returns_409(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Намет")

    def boom():
        raise IntegrityError("DELETE FROM items", {}, Exception("fk violation"))

    from unittest import mock
    with mock.patch.object(Session, "commit", side_effect=boom):
        r = client.delete(f"/items/{item['id']}", headers=org)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Конкуренція: рівно один переможець
# ---------------------------------------------------------------------------

def test_concurrent_assign_single_slot_single_winner(client, auth_headers):
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Палатка", quantity=1)

    results = {}
    barrier = threading.Barrier(2)

    def try_assign(headers, key):
        with TestClient(main.app) as c:
            barrier.wait(timeout=5)
            results[key] = c.post(f"/items/{item['id']}/assign", headers=headers).status_code

    t1 = threading.Thread(target=try_assign, args=(u1, "u1"))
    t2 = threading.Thread(target=try_assign, args=(u2, "u2"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sorted(results.values()) == [200, 400]


def test_concurrent_join_same_invite_multiple_users(client, auth_headers):
    """Інвайт-токен багаторазовий: два різні користувачі можуть приєднатися одночасно."""
    org = auth_headers("org_join")
    trip = client.post("/trips/", json={"title": "Трек"}, headers=org).json()
    token = client.get(f"/trips/{trip['id']}/invite", headers=org).json()["invite_token"]
    u1 = auth_headers("join_one")
    u2 = auth_headers("join_two")

    results = {}
    barrier = threading.Barrier(2)

    def try_join(headers, key):
        with TestClient(main.app) as c:
            barrier.wait(timeout=5)
            results[key] = c.post(f"/trips/invite/{token}", headers=headers).status_code

    t1 = threading.Thread(target=try_join, args=(u1, "u1"))
    t2 = threading.Thread(target=try_join, args=(u2, "u2"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sorted(results.values()) == [200, 200]