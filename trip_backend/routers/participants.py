from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete, func, select, or_
from database import get_db
from deps import get_current_user, user_is_member, get_owned_trip, ensure_active_trip
from rate_limit import limiter
from activity_log import log_activity
import models, schemas
import secrets
router = APIRouter(prefix="/trips")

def _ensure_no_budget_records(
    db: Session,
    trip_id: int,
    user_id: int
):
    has_contribution = (
        db.query(models.Contribution)
        .filter(
            models.Contribution.trip_id == trip_id,
            or_(
                models.Contribution.user_id == user_id,
                models.Contribution.created_by_id == user_id
            )
        )
        .first()
        is not None
    )

    has_expense = (
        db.query(models.Expense)
        .filter(
            models.Expense.trip_id == trip_id,
            or_(
                models.Expense.paid_by_user_id == user_id,
                models.Expense.created_by_id == user_id
            )
        )
        .first()
        is not None
    )

    has_share = (
        db.query(models.ExpenseShare)
        .join(
            models.Expense,
            models.Expense.id == models.ExpenseShare.expense_id
        )
        .filter(
            models.ExpenseShare.user_id == user_id,
            models.Expense.trip_id == trip_id
        )
        .first()
        is not None
    )

    if has_contribution or has_expense or has_share:
        raise HTTPException(status_code=409, detail="Спочатку врегулюйте фінанси учасника (внески/частки)")

@router.get("/{trip_id}/invite", response_model=schemas.InviteTokenResponse)
@limiter.limit("60/minute")
def get_invite_token(
    request: Request,
    trip_id: int,
    trip: models.Trip = Depends(get_owned_trip)
):
    return {"invite_token": trip.invite_token}


@router.post("/{trip_id}/invite", response_model=schemas.InviteTokenResponse)
@limiter.limit("60/minute")
def rotate_invite_token(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_owned_trip)
):
    ensure_active_trip(trip)
    trip.invite_token = secrets.token_urlsafe(32)
    trip.invite_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()
    return {"invite_token": trip.invite_token}


@router.post("/invite/{token}")
@limiter.limit("60/minute")
def join_by_invite_token(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.invite_token == token).first()
    if trip is None or (trip.invite_expires_at is not None and trip.invite_expires_at < datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail="Інвайт-токен недійсний")

    ensure_active_trip(trip)

    if trip.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Ви вже є організатором цієї поїздки")

    if user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=400, detail="Ви вже приєдналися до цієї поїздки")

    try:
        trip.participants.append(current_user)
        log_activity(db, trip.id, current_user.id, "participant_joined", {"username": current_user.username})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ви вже є учасником цієї поїздки")
    
    return {
        "message": "Ви приєдналися до поїздки",
        "trip_id": trip.id,
        "title": trip.title,
    }


@router.get("/invite/{token}/preview")
@limiter.limit("60/minute")
def preview_invite(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    trip = (
        db.query(models.Trip)
        .options(selectinload(models.Trip.owner))
        .filter(models.Trip.invite_token == token)
        .first()
    )
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
@limiter.limit("60/minute")
def remove_participant(
    request: Request,
    trip_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_owned_trip)
):
    ensure_active_trip(trip)
    user_to_remove = db.get(models.User, user_id)
    if not user_to_remove or not user_is_member(db, trip, user_to_remove.id):
        raise HTTPException(status_code=404, detail="Учасника не знайдено в цій поїздці")

    _ensure_no_budget_records(db, trip_id, user_id)

    db.execute(
        delete(models.trip_users).where(
            models.trip_users.c.trip_id == trip.id,
            models.trip_users.c.user_id == user_to_remove.id,
        )
    )
    db.execute(
        delete(models.item_assignments).where(
            models.item_assignments.c.user_id == user_to_remove.id,
            models.item_assignments.c.item_id.in_(
                select(models.Item.id).where(models.Item.trip_id == trip.id)
            ),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")

    return {"message": "Учасника успішно видалено, а його речі звільнено"}

@router.delete("/{trip_id}/leave")
@limiter.limit("60/minute")
def leave_trip(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Вихід учасника із архівної поїздки дозволений свідомо"""
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if not user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=400, detail="Ви не є учасником цієї поїздки")

    if trip.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Організатор не може вийти, він може лише видалити поїздку")

    _ensure_no_budget_records(db, trip_id, current_user.id)

    db.execute(
        delete(models.trip_users).where(
            models.trip_users.c.trip_id == trip.id,
            models.trip_users.c.user_id == current_user.id,
        )
    )
    db.execute(
        delete(models.item_assignments).where(
            models.item_assignments.c.user_id == current_user.id,
            models.item_assignments.c.item_id.in_(
                select(models.Item.id).where(models.Item.trip_id == trip.id)
            ),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Дані змінилися, спробуйте ще раз")

    return {"message": "Ви успішно вийшли з поїздки"}
