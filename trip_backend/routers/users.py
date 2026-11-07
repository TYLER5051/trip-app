from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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

    packing_row = (
        db.query(
            func.count(func.distinct(models.Item.id)).label("total_items"),
            func.count(func.distinct(models.item_assignments.c.item_id)).label("packed_items"),
        )
        .outerjoin(models.item_assignments, models.item_assignments.c.item_id == models.Item.id)
        .filter(
            models.Item.trip.has(
                (models.Trip.owner_id == current_user.id)
                | models.Trip.participants.any(models.User.id == current_user.id)
            )
        )
        .one()
    )

    return {
        "id": current_user.id,
        "username": current_user.username,
        "avatar_color": current_user.avatar_color,
        "owned_trips_count": owned_trips_count or 0,
        "participating_trips_count": participating_trips_count or 0,
        "assigned_items_count": assigned_items_count or 0,
        "total_items_count": packing_row.total_items or 0,
        "packed_items_count": packing_row.packed_items or 0
    }


@router.patch("/me")
@limiter.limit("10/minute")
def change_profile(
    request: Request,
    update_user: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user = db.get(models.User, current_user.id)
    if update_user.username is not None and update_user.username != user.username:
        if not update_user.current_password:
            raise HTTPException(status_code=400, detail="Введіть поточний пароль")
        if not auth.verify_password(update_user.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Невірний поточний пароль")
        user.username = update_user.username
    if update_user.avatar_color is not None:
        user.avatar_color = update_user.avatar_color

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Користувач із таким ім'ям вже існує")
    
    access_token = auth.create_access_token(
        data={"sub": str(user.id), "ver": user.token_version, "username": user.username}
    )
    return {"username": user.username, "avatar_color": user.avatar_color, "access_token": access_token, "token_type": "bearer"}

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