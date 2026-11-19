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


def test_concurrent_quantity_update_vs_assign_invariant(client, auth_headers):
    """Інваріант «розібрано <= quantity» не ламається при одночасних
    update_item(quantity) та assign_item: with_for_update серіалізує обидва
    запити на рядку речі, тож рівно один переможе, інший отримає 400,
    а в кінцевому стані сума призначень не перевищує quantity."""
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Каремат", quantity=5)

    results = {}
    barrier = threading.Barrier(2)

    def try_patch_quantity():
        with TestClient(main.app) as c:
            barrier.wait(timeout=5)
            results["patch"] = c.patch(
                f"/items/{item['id']}",
                json={"quantity": 1},
                headers=org,
            ).status_code

    def try_assign():
        with TestClient(main.app) as c:
            barrier.wait(timeout=5)
            results["assign"] = c.post(
                f"/items/{item['id']}/assign",
                json={"quantity": 5},
                headers=u1,
            ).status_code

    t1 = threading.Thread(target=try_patch_quantity)
    t2 = threading.Thread(target=try_assign)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # quantity=1 і assign=5 несумісні: хто першим став на лок — виграє (200),
    # другий обов'язково відхиляється (400). Обидва успішними бути не можуть.
    assert {results["patch"], results["assign"]} == {200, 400}

    # Пост-перевірка збереженого стану: quantity >= суми призначень.
    items_data = client.get(f"/trips/{trip_id}/items/?limit=100", headers=org).json()["items"]
    fresh = next(i for i in items_data if i["id"] == item["id"])
    assigned = sum(a["quantity"] for a in fresh["assignments"])
    assert fresh["quantity"] >= assigned
    fresh = next(i for i in items_data if i["id"] == item["id"])
    assigned = sum(a["quantity"] for a in fresh["assignments"])
    assert fresh["quantity"] >= assigned

def test_concurrent_delete_vs_assign_consistency(client, auth_headers):
    """Рядковий лок (FOR UPDATE) серіалізує delete/assign:
    - якщо першим устигає delete  -> assign отримує 404 (річ уже немає);
    - якщо першим устигає assign  -> delete успішно видаляє річ, а в історію
      записуються item_unassigned (за кожного учасника) та item_deleted.
    Неприпустимі ні 500, ні хибне 400 «Ви вже взяли цю річ»."""
    trip_id, cat1, cat2, org, u1, u2 = setup_trip(client, auth_headers)
    item = create_item(client, org, trip_id, cat1, "Дощовик", quantity=1)

    results = {}
    barrier = threading.Barrier(2)

    def try_delete():
        with TestClient(main.app) as c:
            barrier.wait(timeout=5)
            results["delete"] = c.delete(f"/items/{item['id']}", headers=org).status_code

    def try_assign():
        with TestClient(main.app) as c:
            barrier.wait(timeout=5)
            results["assign"] = c.post(
                f"/items/{item['id']}/assign",
                json={"quantity": 1},
                headers=u1,
            ).status_code

    t1 = threading.Thread(target=try_delete)
    t2 = threading.Thread(target=try_assign)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    d, a = results["delete"], results["assign"]
    assert d == 200, f"delete має завжди проходити (item існує): {d}"
    assert a in (200, 404), f"assign: 404 якщо річ видалено, інакше 200, отримано {a}"

    # Річ у будь-якому разі видалена
    items_data = client.get(f"/trips/{trip_id}/items/?limit=100", headers=org).json()
    assert all(i["id"] != item["id"] for i in items_data["items"])

    acts = client.get(f"/trips/{trip_id}/activities?limit=50", headers=org).json()["items"]
    deleted = [x for x in acts if x["action"] == "item_deleted"]
    assert len(deleted) == 1, acts

    if a == 200:
        # assign устиг: у історії має бути рівно один item_unassigned — від того,
        # хто видаляв, з деталями призначення (не від того, хто брав річ).
        unassigned = [x for x in acts if x["action"] == "item_unassigned"]
        assert len(unassigned) == 1, acts
        assert unassigned[0]["details"]["quantity"] == 1
        assert unassigned[0]["details"]["name"] == "Дощовик"


MUTATING_ROUTES = [
    ("POST", "/items/"),
    ("PATCH", "/items/{item_id}"),
    ("POST", "/items/{item_id}/assign"),
    ("DELETE", "/items/{item_id}/assign"),
    ("DELETE", "/items/{item_id}"),
    ("POST", "/trips/"),
    ("PATCH", "/trips/{trip_id}"),
    ("POST", "/trips/{trip_id}/categories/"),
    ("PATCH", "/trips/{trip_id}/categories/{category_id}"),
    ("DELETE", "/trips/{trip_id}/categories/{category_id}"),
    ("POST", "/trips/{trip_id}/copy-items"),
    ("PATCH", "/trips/{trip_id}/transfer-owner"),
    ("POST", "/trips/{trip_id}/archive"),
    ("POST", "/trips/{trip_id}/unarchive"),
    ("DELETE", "/trips/{trip_id}"),
    ("POST", "/trips/{trip_id}/invite"),
    ("POST", "/trips/invite/{token}"),
    ("DELETE", "/trips/{trip_id}/participants/{user_id}"),
    ("DELETE", "/trips/{trip_id}/leave"),
    ("PATCH", "/users/me"),
    ("PATCH", "/users/me/password"),
    ("DELETE", "/users/me"),
]


def test_mutating_endpoints_have_rate_limits():
    """Метадата-перевірка: кожен мутаційний ендпоінт обгорнутий @limiter.limit
    slowapi (обгортка має `__wrapped__`). Сам лімітер у тестах вимкнено,
    тому перевіряємо лише факт наявності декоратора."""
    for method, path in MUTATING_ROUTES:
        matches = [
            r for r in main.app.routes
            if getattr(r, "path", None) == path and method in (r.methods or set())
        ]
        assert matches, f"Маршрут {method} {path} не знайдено"
        endpoint = matches[0].endpoint
        assert hasattr(endpoint, "__wrapped__"), f"{method} {path}: rate-limit не виставлено"