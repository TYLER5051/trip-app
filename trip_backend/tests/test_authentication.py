"""
Тести авторизації: реєстрація + різні сценарії логіна.
Розрізняємо:
  - юзера немає АБО пароль невірний -> 401 (щоб не розкривати, чи існує акаунт)
  - все вірно                       -> 200 + access_token
"""
from jose import jwt
import auth 

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

def _token_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _get_me(client, headers):
    r = client.get("/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_token_claims_carry_user_id_and_version(client, auth_headers):
    headers = auth_headers("traveller")
    me = _get_me(client, headers)

    token = headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == str(me["id"])
    assert payload["ver"] == 1


def test_legacy_username_sub_token_rejected(client, auth_headers):
    # Старий формат токена: sub=username, поле ver відсутнє.
    auth_headers("traveller")
    legacy = auth.create_access_token(data={"sub": "traveller"})
    assert client.get("/users/me", headers=_token_headers(legacy)).status_code == 401


def test_token_without_sub_rejected(client, auth_headers):
    auth_headers("traveller")
    token = auth.create_access_token(data={"ver": 1})
    assert client.get("/users/me", headers=_token_headers(token)).status_code == 401


def test_token_with_stale_version_rejected(client, auth_headers):
    # Правильний id, але застаріла версія токена -> сесія невалідна.
    headers = auth_headers("traveller")
    me = _get_me(client, headers)

    stale = auth.create_access_token(data={"sub": str(me["id"]), "ver": 999})
    assert client.get("/users/me", headers=_token_headers(stale)).status_code == 401
