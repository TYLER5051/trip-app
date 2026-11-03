from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from deps import get_current_user
from rate_limit import limiter
import auth, models, schemas

router = APIRouter(prefix="/users")

@router.get("/me", response_model=schemas.UserMeResponse)
def get_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    owned_trips_count = (
        db.query(func.count(models.Trip.id))
        .filter(models.Trip.owner_id == current_user.id)
        .scalar()
    )
    participating_trips_count = (
        db.query(func.count(models.trip_users.c.trip_id))
        .filter(models.trip_users.c.user_id == current_user.id)
        .scalar()
    )
    assigned_items_count = (
        db.query(func.count(models.item_assignments.c.item_id))
        .filter(models.item_assignments.c.user_id == current_user.id)
        .scalar()
    )

    return {
        "id": current_user.id,
        "username": current_user.username,
        "owned_trips_count": owned_trips_count or 0,
        "participating_trips_count": participating_trips_count or 0,
        "assigned_items_count": assigned_items_count or 0,
    }


@router.patch("/me/password")
@limiter.limit("10/minute")
def change_password(
    request: Request,
    pwd_request: schemas.PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not auth.verify_password(pwd_request.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Неправильний пароль")

    current_user.hashed_password = auth.get_password_hash(pwd_request.new_password)
    db.commit()

    return {"message": "Пароль успішно змінено"}