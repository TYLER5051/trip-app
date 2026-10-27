"""
Налаштування pytest для бекенду.

Запуск тестів (з папки trip_backend):
    venv/Scripts/python -m pytest tests -v

ВАЖЛИВО: перед запуском має бути піднята БД:
    docker compose up -d db
"""
import os
import sys

# Кладемо корінь бекенду (тут лежать main.py, models.py, ...) у sys.path,
# щоб python міг робити "import main" з тестів.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import main  # noqa: F401  (тут же спрацьовує models.Base.metadata.create_all)
from database import engine

main.app.state.limiter.enabled = False

# Таблиці, які будемо чистити перед кожним тестом.
# Порядок важливий: спочатку залежні таблиці, потім батьківські.
TABLES = ["item_assignments", "items", "categories", "trip_users", "trips", "users"]


def _cleanup():
    """Очищає всі таблиці та скидає лічильники id (щоб id не росли між тестами)."""
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
        for table in ["items", "categories", "trips", "users"]:
            conn.execute(text(
                "SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {t}".format(t=table)
            ))


@pytest.fixture(scope="session")
def client():
    """Клієнт, який «ходить» у наш API замість браузера (без HTTP-сервера)."""
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_db():
    """Гарантує, що кожен тест починається з порожньої БД."""
    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def auth_headers(client):
    """
    Повертає функцію, яка реєструє користувача і повертає заголовки
    з Bearer-токеном (так само робить фронтенд після логіну).
    """
    def _make(username, password="password123"):
        r = client.post("/register", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        r = client.post("/login", data={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _make
