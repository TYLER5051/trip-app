"""
Тести терміну дії інвайт-токена.

  - при створенні поїздки токен отримує дедлайн (30 днів);
  - приєднання та прев'ю за простроченим токеном повертають 404;
  - ротація токена продовжує термін дії.
"""
from datetime import datetime, timezone
from sqlalchemy import text
from database import engine


def create_trip(client, headers):
    r = client.post("/trips/", json={"title": "Похід"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def invite_token_of(client, trip_id, headers):
    r = client.get(f"/trips/{trip_id}/invite", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["invite_token"]


def set_token_expired(trip_id):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE trips SET invite_expires_at = NOW() - INTERVAL '1 day' WHERE id = :tid"),
            {"tid": trip_id},
        )


def test_fresh_token_has_long_expiry(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org)

    with engine.connect() as conn:
        expires = conn.execute(
            text("SELECT invite_expires_at FROM trips WHERE id = :tid"), {"tid": trip["id"]}
        ).scalar_one()

    assert expires is not None
    assert expires > datetime.now(timezone.utc)


def test_fresh_token_still_joins(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    r = client.post(f"/trips/invite/{token}", headers=guest)
    assert r.status_code == 200, r.text
    assert r.json()["trip_id"] == trip["id"]


def test_expired_token_cannot_be_used(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    set_token_expired(trip["id"])

    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 404
    assert client.get(f"/trips/invite/{token}/preview").status_code == 404


def test_rotation_renews_expiry(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org)
    token = invite_token_of(client, trip["id"], org)

    set_token_expired(trip["id"])
    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 404

    new_token = client.post(f"/trips/{trip['id']}/invite", headers=org).json()["invite_token"]
    assert new_token != token
    assert client.post(f"/trips/invite/{new_token}", headers=guest).status_code == 200