"""
Валідація PATCH /trips/{id} (регресія п.3 аудиту):
  - назва коротша за 3 символи або довша за 100 → 422;
  - пробільна назва → 422 (str_strip_whitespace);
  - коректна назва застосовується (з тримінгом пробілів),
    дати патчаться незалежно від назви.
"""


def create_trip(client, headers, title):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_patch_title_too_short_rejected(client, auth_headers):
    org = auth_headers("title_short")
    trip = create_trip(client, org, "Похід")

    r = client.patch(f"/trips/{trip['id']}", json={"title": "аб"}, headers=org)
    assert r.status_code == 422


def test_patch_title_too_long_rejected(client, auth_headers):
    org = auth_headers("title_long")
    trip = create_trip(client, org, "Похід")

    r = client.patch(f"/trips/{trip['id']}", json={"title": "л" * 101}, headers=org)
    assert r.status_code == 422


def test_patch_title_whitespace_only_rejected(client, auth_headers):
    org = auth_headers("title_blank")
    trip = create_trip(client, org, "Похід")

    r = client.patch(f"/trips/{trip['id']}", json={"title": "   "}, headers=org)
    assert r.status_code == 422


def test_patch_title_valid_is_trimmed_and_applied(client, auth_headers):
    org = auth_headers("title_ok")
    trip = create_trip(client, org, "Похід")

    r = client.patch(f"/trips/{trip['id']}", json={"title": "   Великий похід   "}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Великий похід"


def test_patch_title_alongside_dates(client, auth_headers):
    org = auth_headers("title_dates")
    trip = create_trip(client, org, "Похід")

    r = client.patch(
        f"/trips/{trip['id']}",
        json={"title": "Нова назва", "start_date": "2026-07-01"},
        headers=org,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Нова назва"
    assert body["start_date"] == "2026-07-01"