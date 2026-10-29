"""
Тести серверного пошуку та пагінації GET /trips/?q=&limit=&offset=.

  - q фільтрує по назві регістронезалежно (ILIKE), до пагінації;
  - total відображає кількість поїздок після фільтра q (не розмір сторінки);
  - limit/offset повертають правильну сторінку при стабільному порядку;
  - невалідні limit/offset → 422.
"""


def create_trip(client, headers, title):
    r = client.post("/trips/", json={"title": title}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def get_trips(client, headers, **params):
    r = client.get("/trips/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_search_by_title_case_insensitive(client, auth_headers):
    org = auth_headers("org")
    create_trip(client, org, "Альпийський похід")
    create_trip(client, org, "Велосипедна подорож")
    create_trip(client, org, "Похід у Карпати")

    res = get_trips(client, org, q="похід")
    assert res["total"] == 2
    assert sorted(t["title"] for t in res["items"]) == ["Альпийський похід", "Похід у Карпати"]

    res_upper = get_trips(client, org, q="ПОХІД")
    assert res_upper["total"] == 2

    res_none = get_trips(client, org, q="космос")
    assert res_none["total"] == 0
    assert res_none["items"] == []


def test_empty_and_whitespace_q_ignored(client, auth_headers):
    org = auth_headers("org")
    create_trip(client, org, "Похід")

    for q in ("", "   "):
        res = get_trips(client, org, q=q)
        assert res["total"] == 1
        assert [t["title"] for t in res["items"]] == ["Похід"]


def test_pagination_limit_offset_and_total(client, auth_headers):
    org = auth_headers("org")
    for i in range(1, 4):
        create_trip(client, org, f"Поїздка {i}")

    res = get_trips(client, org, limit=2)
    assert res["total"] == 3
    assert len(res["items"]) == 2
    assert res["limit"] == 2
    assert res["offset"] == 0

    res2 = get_trips(client, org, limit=2, offset=2)
    assert res2["total"] == 3
    assert len(res2["items"]) == 1
    assert res2["offset"] == 2

    # Сторінки не перетинаються і не пропускають поїздок
    ids = [t["id"] for t in res["items"]] + [t["id"] for t in res2["items"]]
    assert len(set(ids)) == 3

    res3 = get_trips(client, org, offset=10)
    assert res3["total"] == 3
    assert res3["items"] == []


def test_search_combined_with_pagination(client, auth_headers):
    org = auth_headers("org")
    create_trip(client, org, "Похід перший")
    create_trip(client, org, "Похід другий")
    create_trip(client, org, "Риболовля")

    res = get_trips(client, org, q="Похід", limit=1, offset=1)
    assert res["total"] == 2
    assert len(res["items"]) == 1


def test_search_only_within_accessible_trips(client, auth_headers):
    org = auth_headers("org")
    guest = auth_headers("guest")
    trip = create_trip(client, org, "Приватний похід")

    res_org = get_trips(client, org, q="Приватний")
    assert res_org["total"] == 1
    assert res_org["items"][0]["id"] == trip["id"]

    res_guest = get_trips(client, guest, q="Приватний")
    assert res_guest["total"] == 0


def test_invalid_pagination_params_rejected(client, auth_headers):
    org = auth_headers("org")

    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        r = client.get("/trips/", headers=org, params=params)
        assert r.status_code == 422, params

    r = client.get("/trips/", headers=org, params={"limit": 100, "offset": 0})
    assert r.status_code == 200