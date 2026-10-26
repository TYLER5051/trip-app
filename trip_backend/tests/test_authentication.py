"""
Тести авторизації: реєстрація + різні сценарії логіна.
Розрізняємо:
  - юзера немає АБО пароль невірний -> 401 (щоб не розкривати, чи існує акаунт)
  - все вірно                       -> 200 + access_token
"""


def test_register_and_login_success(client, auth_headers):
    auth_headers("test_user")  # одразу реєструє користувача

    r = client.post("/login", data={"username": "test_user", "password": "password123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, auth_headers):
    auth_headers("test_user")

    r = client.post("/login", data={"username": "test_user", "password": "nespravnyi-parol"})
    assert r.status_code == 401
    assert "пароль" in r.json()["detail"].lower()


def test_login_unknown_user(client):
    # Юзера не реєструємо — він «не існує»
    r = client.post("/login", data={"username": "nobody", "password": "password123"})
    assert r.status_code == 401
    assert "логін" in r.json()["detail"].lower()
