from datetime import datetime, timezone, timedelta
from jose import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY не задано. Додайте змінну SECRET_KEY у файл .env")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Перевіряє, чи співпадає введений пароль із зашифрованим у базі."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Шифрує пароль перед тим, як зберегти його в базу."""
    return pwd_context.hash(password)

def create_access_token(data: dict):
    """Генерує JWT-токен (перепустку) для користувача."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt