"""
Тести Фічі 15: дати поїздки та архівація.

  - створення поїздки з датами / без дат; валідація start <= end;
  - PATCH дат (зміна/очищення), невалідна пара → 422;
  - archive/unarchive: тільки організатор; поїздка зникає зі звичайного
    списку і з'являється у role=archived; розархів повертає її назад;
  - архівні поїздки не потрапляють у пошук без role=archived;
  - архівовану поїздку все ще можна відкрити (GET /trips/{id}).
"""


def create_trip(client, headers, title, **extra):
    payload = {"title": title, **extra}
    r = client.post("/trips/", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_trip_with_dates(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Похід", start_date="2026-06-01", end_date="2026-06-07")
    assert trip["start_date"] == "2026-06-01"
    assert trip["end_date"] == "2026-06-07"
    assert trip["is_archived"] is False


def test_create_trip_without_dates_still_works(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Без дат")
    assert trip["start_date"] is None
    assert trip["end_date"] is None
    assert trip["is_archived"] is False


def test_create_trip_inverted_dates_rejected(client, auth_headers):
    org = auth_headers("org")
    r = client.post(
        "/trips/",
        json={"title": "Похід", "start_date": "2026-06-07", "end_date": "2026-06-01"},
        headers=org,
    )
    assert r.status_code == 422


def test_equal_dates_allowed(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Одноденний похід", start_date="2026-06-07", end_date="2026-06-07")
    assert trip["start_date"] == "2026-06-07"
    assert trip["end_date"] == "2026-06-07"


def test_update_dates_and_clear_them(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Похід", start_date="2026-06-01", end_date="2026-06-07")

    r = client.patch(f"/trips/{trip['id']}", json={"start_date": "2026-06-02"}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["start_date"] == "2026-06-02"
    assert r.json()["end_date"] == "2026-06-07"

    # явний null очищає дату без зачіпання іншої
    r = client.patch(f"/trips/{trip['id']}", json={"end_date": None}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["start_date"] == "2026-06-02"
    assert r.json()["end_date"] is None


def test_update_trip_inverted_dates_rejected(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Похід", start_date="2026-06-01", end_date="2026-06-07")
    r = client.patch(f"/trips/{trip['id']}", json={"start_date": "2026-06-10"}, headers=org)
    assert r.status_code == 422


def test_archive_hides_trip_and_unarchive_restores(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Похід що завершився")

    r = client.post(f"/trips/{trip['id']}/archive", headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["is_archived"] is True

    lst = client.get("/trips/", headers=org).json()
    assert lst["total"] == 0
    assert all(t["id"] != trip["id"] for t in lst["items"])

    arch = client.get("/trips/", headers=org, params={"role": "archived"}).json()
    assert [t["id"] for t in arch["items"]] == [trip["id"]]

    r = client.post(f"/trips/{trip['id']}/unarchive", headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["is_archived"] is False

    lst = client.get("/trips/", headers=org).json()
    assert [t["id"] for t in lst["items"]] == [trip["id"]]


def test_archived_trip_visible_in_owned_and_joined_roles(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org, "Похід з гостем")

    token = client.get(f"/trips/{trip['id']}/invite", headers=org).json()["invite_token"]
    assert client.post(f"/trips/invite/{token}", headers=guest).status_code == 200
    client.post(f"/trips/{trip['id']}/archive", headers=org)

    # архівна вкладка показує поїздку і для організатора, і для учасника
    owned_arch = client.get("/trips/", headers=org, params={"role": "archived"}).json()
    joined_arch = client.get("/trips/", headers=guest, params={"role": "archived"}).json()
    assert [t["id"] for t in owned_arch["items"]] == [trip["id"]]
    assert [t["id"] for t in joined_arch["items"]] == [trip["id"]]

    # і вона не показується в активних ні тому, ні іншому
    assert client.get("/trips/", headers=org).json()["total"] == 0
    assert client.get("/trips/", headers=guest).json()["total"] == 0


def test_archive_search_excludes_archived_by_default(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Спеціальний похід")
    client.post(f"/trips/{trip['id']}/archive", headers=org)

    assert client.get("/trips/", headers=org, params={"q": "Спеціальний"}).json()["total"] == 0
    arch = client.get("/trips/", headers=org, params={"role": "archived", "q": "Спеціальний"}).json()
    assert arch["total"] == 1


def test_only_owner_can_archive(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org, "Чужий похід")

    assert client.post(f"/trips/{trip['id']}/archive", headers=guest).status_code == 403
    assert client.post(f"/trips/{trip['id']}/unarchive", headers=guest).status_code == 403


def test_archived_trip_still_accessible(client, auth_headers):
    org = auth_headers("org")
    trip = create_trip(client, org, "Архівний відкрию")
    client.post(f"/trips/{trip['id']}/archive", headers=org)

    detail = client.get(f"/trips/{trip['id']}", headers=org)
    assert detail.status_code == 200
    assert detail.json()["is_archived"] is True