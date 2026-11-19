from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session, selectinload

from database import get_db
import auth
import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

_ITEM_LOAD_OPTIONS = (
    selectinload(models.Item.assignments).selectinload(models.ItemAssignment.user),
    selectinload(models.Item.created_by),
    selectinload(models.Item.category).selectinload(models.Category.created_by),
)

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
):
    """Повертає авторизованого користувача або 401."""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Не вдалося підтвердити авторизацію",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if payload.get("ver") != user.token_version:
        raise credentials_exception
    return user

def user_is_member(
    db: Session, 
    trip, 
    user_id: int
) -> bool:
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

def get_accessible_trip(
    trip_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    trip = db.query(models.Trip).options(
        selectinload(models.Trip.owner),
        selectinload(models.Trip.participants)
    ).filter(models.Trip.id == trip_id).first()

    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and not user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    return trip

def get_owned_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> models.Trip:
    trip = db.query(models.Trip).options(
        selectinload(models.Trip.owner),
        selectinload(models.Trip.participants)
    ).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    if trip.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Тільки організатор має доступ")
    return trip

def ensure_active_trip(
    trip: models.Trip
):
    if trip.is_archived:
        raise HTTPException(status_code=400, detail="Поїздку архівовано — зміни недоступні")

def reload_item(
    item_id: int,
    db: Session
):
    item = (
        db.query(models.Item)
        .filter(models.Item.id == item_id)
        .options(*_ITEM_LOAD_OPTIONS)
        .populate_existing()
        .first()
    )

    return item

def get_trip_item(
    item_id: int,
    db: Session,
    current_user: models.User,
    for_update: bool = False
) -> tuple[models.Item, models.Trip]:
    if for_update:
        item = db.query(models.Item).filter(models.Item.id == item_id).with_for_update().first()
    else:
        item = db.get(models.Item, item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = get_accessible_trip(item.trip_id, db, current_user)

    return (item, trip)