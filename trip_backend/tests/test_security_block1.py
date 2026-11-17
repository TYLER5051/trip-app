import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from database import SessionLocal

CRITICAL_ITEM = "Паспорт"
COMMON_PASSWORD = "password123"


def _make_trip(client, headers, title="Поїздка"):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _make_category(client, headers, trip_id):
    r = client.post(f"/trips/{trip_id}/categories/", json={"name": "Документи"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _item_payload(trip_id, cat_id, **overrides):
    payload = {"name": "Намет", "trip_id": trip_id, "category_id": cat_id}
    payload.update(overrides)
    return payload


# ---- C1: порядок перевірок прав у delete_item ----

def test_outsider_delete_critical_item_gets_403_not_400(client, auth_headers):
    """Сторонній користувач НЕ має змоги за статусом 400 дізнатися,
    що річ критична: до перевірки is_critical спочатку йде перевірка прав."""
    org = auth_headers("owner_c1")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)
    r = client.post("/items/", json=_item_payload(
        trip_id, cat_id, name=CRITICAL_ITEM, is_critical=True
    ), headers=org)
    assert r.status_code == 200, r.text
    item_id = r.json()["id"]

    outsider_headers = auth_headers("outsider1")

    # і критична...
    r = client.delete(f"/items/{item_id}", headers=outsider_headers)
    assert r.status_code == 403, r.text
    # ...і некритична річ дають той самий 403 — без витоку стану is_critical
    r2 = client.post("/items/", json=_item_payload(trip_id, cat_id, name="Крем від засмаги"),
                     headers=org)
    assert r2.status_code == 200, r2.text
    r = client.delete(f"/items/{r2.json()['id']}", headers=outsider_headers)
    assert r.status_code == 403, r.text


def test_owner_still_cannot_delete_critical_item(client, auth_headers):
    """Регресія: власник як і раніше отримує 400 для критичної речі."""
    org = auth_headers("owner_c2")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)
    r = client.post("/items/", json=_item_payload(
        trip_id, cat_id, name=CRITICAL_ITEM, is_critical=True
    ), headers=org)
    item_id = r.json()["id"]

    r = client.delete(f"/items/{item_id}", headers=org)
    assert r.status_code == 400, r.text


# ---- C2 / M5: валідація реєстрації ----

@pytest.mark.parametrize("bad_username", ["ab", "a b", "bad user!", "user🙂", "x" * 31])
def test_register_invalid_username_rejected(client, bad_username):
    """Патерн username працює і на реєстрації, не лише на PATCH /users/me."""
    r = client.post("/register", json={"username": bad_username, "password": COMMON_PASSWORD})
    assert r.status_code == 422, r.text


def test_register_password_longer_than_72_rejected(client):
    """bcrypt мовчки обрізає пароль на 72 байти — такі паролі треба відхиляти."""
    r = client.post("/register", json={"username": "longpwd", "password": "a" * 73})
    assert r.status_code == 422, r.text


def test_register_valid_username_with_dash_underscore_ok(client):
    r = client.post("/register", json={"username": "good-name_1", "password": COMMON_PASSWORD})
    assert r.status_code == 200, r.text


# ---- C3: межі quantity (схема + рівень БД) ----

def test_create_item_quantity_above_1000_rejected(client, auth_headers):
    org = auth_headers("owner_c3")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)

    r = client.post("/items/", json=_item_payload(trip_id, cat_id, quantity=1001), headers=org)
    assert r.status_code == 422, r.text


def test_update_item_quantity_above_1000_rejected(client, auth_headers):
    org = auth_headers("owner_c4")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)
    r = client.post("/items/", json=_item_payload(trip_id, cat_id), headers=org)
    item_id = r.json()["id"]

    r = client.patch(f"/items/{item_id}", json={"quantity": 1001}, headers=org)
    assert r.status_code == 422, r.text


def test_assign_quantity_above_1000_rejected(client, auth_headers):
    org = auth_headers("owner_c5")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)
    r = client.post("/items/", json=_item_payload(trip_id, cat_id), headers=org)
    item_id = r.json()["id"]

    r = client.post(f"/items/{item_id}/assign", json={"quantity": 1001}, headers=org)
    assert r.status_code == 422, r.text


def test_db_rejects_item_quantity_below_one(client, auth_headers):
    """Прямий запис quantity = 0 минаючи ORM блокується CheckConstraint."""
    org = auth_headers("db_owner_items")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)
    r = client.post("/items/", json=_item_payload(trip_id, cat_id), headers=org)
    assert r.status_code == 200

    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                text("INSERT INTO items (name, quantity, note, is_critical, trip_id, category_id) "
                     "VALUES ('Погана річ', 0, NULL, FALSE, :trip_id, NULL)"),
                {"trip_id": trip_id},
            )
            db.rollback()


def test_db_rejects_assignment_quantity_below_one(client, auth_headers):
    """CheckConstraint на item_assignments: quantity = 0 неможливо записати напряму."""
    org = auth_headers("db_owner_assignments")
    trip_id = _make_trip(client, org)
    cat_id = _make_category(client, org, trip_id)
    r = client.post("/items/", json=_item_payload(trip_id, cat_id), headers=org)
    item_id = r.json()["id"]

    with SessionLocal() as db:
        user_id = db.execute(
            text("SELECT id FROM users WHERE username = 'db_owner_assignments'")
        ).scalar()
        with pytest.raises(IntegrityError):
            db.execute(
                text("INSERT INTO item_assignments (item_id, user_id, quantity) "
                     "VALUES (:item_id, :user_id, 0)"),
                {"item_id": item_id, "user_id": user_id},
            )
            db.rollback()


# ---- C5 / M10: /login повертає username; /logout інвалідує токен ----

def test_login_response_contains_username(client):
    client.post("/register", json={"username": "carol", "password": COMMON_PASSWORD})
    r = client.post("/login", data={"username": "carol", "password": COMMON_PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "carol"


def test_logout_invalidates_old_token(client, auth_headers):
    headers = auth_headers("dave")

    r = client.post("/logout", headers=headers)
    assert r.status_code == 200, r.text

    # Стара сесія більше не діє
    r = client.get("/users/me", headers=headers)
    assert r.status_code == 401, r.text

    # А користувач не зник із БД — можна увійти знову
    r = client.post("/login", data={"username": "dave", "password": COMMON_PASSWORD})
    assert r.status_code == 200, r.text
    new_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get("/users/me", headers=new_headers)
    assert r.status_code == 200, r.text


def test_logout_requires_auth(client):
    r = client.post("/logout")
    assert r.status_code == 401, r.text