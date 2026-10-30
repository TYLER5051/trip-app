from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
import auth
import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Повертає авторизованого користувача або 401."""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Не вдалося підтвердити авторизацію",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def user_is_member(db: Session, trip, user_id: int) -> bool:
    """Чи є user_id учасником trip — EXISTS по асоціативній таблиці,
    без завантаження всього списку participants у пам'ять."""
    return (
        db.query(models.trip_users.c.user_id)
        .filter(
            models.trip_users.c.trip_id == trip.id,
            models.trip_users.c.user_id == user_id,
        )
        .first()
        is not None
    )

def get_accessible_trip(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and not user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    return trip