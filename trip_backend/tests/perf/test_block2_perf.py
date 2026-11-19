"""
Блок 2: регресії продуктивності/цілісності даних.

  P1 — після expire_on_commit=False: PATCH /trips/{id}/transfer-owner і
       PATCH /trips/{id} повертають свіжі дані (нового власника, оновлену назву).
  P2 — видалення поїздки з речами/категоріями/призначеннями не залишає
       «сирітських» записів у items, categories, item_assignments, trip_users.
"""
from sqlalchemy import text, bindparam

from database import engine


def _setup_full_trip(client, auth_headers):
    """Поїздка з учасником, 2 категоріями, взяттям речі. Повертає dict id."""
    org = auth_headers("org_p2")
    part = auth_headers("part_p2")

    r = client.post("/trips/", json={"title": "Гори"}, headers=org)
    assert r.status_code == 200, r.text
    trip_id = r.json()["id"]

    token = client.get(f"/trips/{trip_id}/invite", headers=org).json()["invite_token"]
    r = client.post(f"/trips/invite/{token}", headers=part)
    assert r.status_code == 200, r.text

    cat1 = client.post(f"/trips/{trip_id}/categories/", json={"name": "Спорядження"}, headers=org).json()
    cat2 = client.post(f"/trips/{trip_id}/categories/", json={"name": "Харчі"}, headers=org).json()

    item1 = client.post("/items/", json={
        "name": "Намет", "trip_id": trip_id, "category_id": cat1["id"], "quantity": 2
    }, headers=org).json()
    item2 = client.post("/items/", json={
        "name": "Крупа", "trip_id": trip_id, "category_id": cat2["id"], "quantity": 3
    }, headers=part).json()

    r = client.post(f"/items/{item1['id']}/assign", json={"quantity": 1}, headers=part)
    assert r.status_code == 200, r.text

    return {
        "org": org,
        "part": part,
        "trip_id": trip_id,
        "cat_ids": [cat1["id"], cat2["id"]],
        "item_ids": [item1["id"], item2["id"]],
    }


def _count(conn, sql, **params):
    stmt = text(sql)
    for name, value in params.items():
        if isinstance(value, tuple):
            stmt = stmt.bindparams(bindparam(name, expanding=True))
    return conn.execute(stmt, params).scalar()

def test_transfer_owner_response_bears_new_owner(client, auth_headers):
    """Регресія: після cmimi власника відповідь PATCH має показувати вже
    НОВОГО власника (owner), а старого — у списку учасників."""
    data = _setup_full_trip(client, auth_headers)
    trip_id, org, part = data["trip_id"], data["org"], data["part"]

    me_org = client.get("/users/me", headers=org).json()
    me_part = client.get("/users/me", headers=part).json()

    r = client.patch(
        f"/trips/{trip_id}/transfer-owner",
        json={"new_owner_id": me_part["id"]},
        headers=org,
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["owner"]["id"] == me_part["id"], (
        f"owner має бути новий власник ({me_part['id']}), отримано {body.get('owner')}"
    )
    part_ids = {p["id"] for p in body["participants"]}
    assert me_part["id"] not in part_ids, "новий власник не має бути в participants"
    assert me_org["id"] in part_ids, "старий власник має бути в participants"

    # Контрольний запит — те саме бачимо через GET
    r = client.get(f"/trips/{trip_id}", headers=org)
    assert r.status_code == 200
    assert r.json()["owner"]["id"] == me_part["id"]


def test_update_trip_response_fresh_after_commit(client, auth_headers):
    """Регресія expire_on_commit=False: PATCH title/дати віддає оновлене
    значення + не втрачає завантажені зв'язки (owner/participants)."""
    data = _setup_full_trip(client, auth_headers)
    trip_id, org = data["trip_id"], data["org"]

    r = client.patch(f"/trips/{trip_id}", json={"title": "Гори-2026"}, headers=org)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Гори-2026", body
    assert body["owner"] is not None, "owner не мав загубитися після commit"

def test_delete_trip_cascades_everything(client, auth_headers):
    """Видалення поїздки з каскадними FK (P2) не залишає сиріт."""
    data = _setup_full_trip(client, auth_headers)
    trip_id = data["trip_id"]
    cat_ids = data["cat_ids"]
    item_ids = data["item_ids"]

    r = client.delete(f"/trips/{trip_id}", headers=data["org"])
    assert r.status_code == 200, r.text

    with engine.connect() as conn:
        assert _count(conn, "SELECT count(*) FROM items WHERE id IN :ids",
                      ids=tuple(item_ids)) == 0
        assert _count(conn, "SELECT count(*) FROM categories WHERE id IN :ids",
                      ids=tuple(cat_ids)) == 0
        assert _count(conn,
                      "SELECT count(*) FROM item_assignments WHERE item_id IN :ids",
                      ids=tuple(item_ids)) == 0
        assert _count(conn, "SELECT count(*) FROM trip_users WHERE trip_id = :t",
                      t=trip_id) == 0
        assert _count(conn, "SELECT count(*) FROM activities WHERE trip_id = :t",
                      t=trip_id) == 0
        assert _count(conn, "SELECT count(*) FROM trips WHERE id = :t", t=trip_id) == 0
