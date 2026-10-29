from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete, func, select
from database import get_db
from deps import get_current_user
from permissions import user_is_member
import models, schemas
import secrets

router = APIRouter(prefix="/trips")


@router.get("/{trip_id}/invite", response_model=schemas.InviteTokenResponse)
def get_invite_token(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    if trip.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Тільки організатор може отримати інвайт-токен")

    return {"invite_token": trip.invite_token}


@router.post("/{trip_id}/invite", response_model=schemas.InviteTokenResponse)
def rotate_invite_token(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    if trip.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Тільки організатор може змінити інвайт-токен")

    trip.invite_token = secrets.token_urlsafe(32)
    trip.invite_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()
    return {"invite_token": trip.invite_token}


@router.post("/invite/{token}")
def join_by_invite_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.invite_token == token).first()
    if trip is None or (trip.invite_expires_at is not None and trip.invite_expires_at < datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail="Інвайт-токен недійсний")

    if trip.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Ви вже є організатором цієї поїздки")

    if user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=400, detail="Ви вже приєдналися до цієї поїздки")

    trip.participants.append(current_user)
    db.commit()
    return {
        "message": "Ви приєдналися до поїздки",
        "trip_id": trip.id,
        "title": trip.title,
    }


@router.get("/invite/{token}/preview")
def preview_invite(token: str, db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.invite_token == token).first()
    if trip is None or (trip.invite_expires_at is not None and trip.invite_expires_at < datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail="Інвайт-токен недійсний")

    participants_count = (
        db.query(func.count(models.trip_users.c.user_id))
        .filter(models.trip_users.c.trip_id == trip.id)
        .scalar()
    )
    items_count = (
        db.query(func.count(models.Item.id))
        .filter(models.Item.trip_id == trip.id)
        .scalar()
    )

    return {
        "id": trip.id,
        "title": trip.title,
        "owner": {"username": trip.owner.username} if trip.owner else None,
        "participants_count": participants_count,
        "items_count": items_count
    }


@router.delete("/{trip_id}/participants/{user_id}")
def remove_participant(
    trip_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if trip_db is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip_db.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Тільки організатор може видаляти учасників"
        )

    user_to_remove = db.get(models.User, user_id)
    if not user_to_remove or not user_is_member(db, trip_db, user_to_remove.id):
        raise HTTPException(status_code=404, detail="Учасника не знайдено в цій поїздці")

    # Членство та взяті речі учасника видаляємо bulk-запитами,
    # без завантаження всіх items/assigned_users у пам'ять.
    db.execute(
        delete(models.trip_users).where(
            models.trip_users.c.trip_id == trip_db.id,
            models.trip_users.c.user_id == user_to_remove.id,
        )
    )
    db.execute(
        delete(models.item_assignments).where(
            models.item_assignments.c.user_id == user_to_remove.id,
            models.item_assignments.c.item_id.in_(
                select(models.Item.id).where(models.Item.trip_id == trip_db.id)
            ),
        )
    )
    db.commit()

    return {"message": "Учасника успішно видалено, а його речі звільнено"}

@router.delete("/{trip_id}/leave")
def leave_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if trip_db is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if not user_is_member(db, trip_db, current_user.id):
        raise HTTPException(status_code=400, detail="Ви не є учасником цієї поїздки")

    if trip_db.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Організатор не може вийти, він може лише видалити поїздку")

    db.execute(
        delete(models.trip_users).where(
            models.trip_users.c.trip_id == trip_db.id,
            models.trip_users.c.user_id == current_user.id,
        )
    )
    db.execute(
        delete(models.item_assignments).where(
            models.item_assignments.c.user_id == current_user.id,
            models.item_assignments.c.item_id.in_(
                select(models.Item.id).where(models.Item.trip_id == trip_db.id)
            ),
        )
    )
    db.commit()

    return {"message": "Ви успішно вийшли з поїздки"}
