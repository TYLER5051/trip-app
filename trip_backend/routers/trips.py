from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
from database import get_db
from deps import get_current_user, get_accessible_trip, get_owned_trip, user_is_member
from rate_limit import limiter
from typing import List, Optional
import models, schemas
import secrets

router = APIRouter(prefix="/trips")

_ITEM_LOAD_OPTIONS = (
    selectinload(models.Item.assigned_users),
    selectinload(models.Item.created_by),
    selectinload(models.Item.category).selectinload(models.Category.created_by),
)

def _stats_for_trip(db: Session, trip_id: int):
    """Підраховує total_items/packed_items одним агрегованим запитом —
    без завантаження всього списку речей у пам'ять."""
    row = (
        db.query(
            func.count(func.distinct(models.Item.id)).label("total_items"),
            func.count(func.distinct(models.item_assignments.c.item_id)).label("packed_items"),
        )
        .outerjoin(models.item_assignments, models.item_assignments.c.item_id == models.Item.id)
        .filter(models.Item.trip_id == trip_id)
        .one()
    )
    return row.total_items, row.packed_items

@router.post("/", response_model=schemas.TripDetailResponse)
def create_trip(
    trip: schemas.TripCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_trip = models.Trip(
        title=trip.title,
        owner_id=current_user.id,
        invite_token=secrets.token_urlsafe(32),
        invite_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )

    db.add(db_trip)
    db.commit()

    created = (
        db.query(models.Trip)
        .options(
            selectinload(models.Trip.owner),
            selectinload(models.Trip.participants),
        )
        .filter(models.Trip.id == db_trip.id)
        .first()
    )
    created.total_items, created.packed_items = _stats_for_trip(db, db_trip.id)
    return created

@router.get("/", response_model=schemas.TripListResponse)
@limiter.limit("100/minute")
def get_trips(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    q: Optional[str] = Query(default=None, max_length=100),
    role: Optional[str] = Query(default=None, pattern="^(owned|joined)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    query_text = q.strip() if q else ""
    base = db.query(models.Trip).filter(
        or_(
            models.Trip.owner_id == current_user.id,
            models.Trip.participants.any(models.User.id == current_user.id),
        )
    )

    if role == "owned":
        base = base.filter(models.Trip.owner_id == current_user.id)
    elif role == "joined":
        base = base.filter(
            models.Trip.owner_id != current_user.id,
            models.Trip.participants.any(models.User.id == current_user.id),
        )

    if query_text:
        escaped = query_text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        base = base.filter(models.Trip.title.ilike(f"%{escaped}%", escape="\\"))

    total = base.count()
    
    trips = (
        base.options(
            selectinload(models.Trip.owner),
        )
        .order_by(
            case((models.Trip.owner_id == current_user.id, 0), else_=1),
            models.Trip.id,
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    trip_ids = [t.id for t in trips]
    stats_rows = (
        db.query(
            models.Item.trip_id,
            func.count(func.distinct(models.Item.id)).label("total_items"),
            func.count(func.distinct(models.item_assignments.c.item_id)).label("packed_items"),
        )
        .outerjoin(models.item_assignments, models.item_assignments.c.item_id == models.Item.id)
        .filter(models.Item.trip_id.in_(trip_ids))
        .group_by(models.Item.trip_id)
        .all()
    )
    participant_rows = (
        db.query(
            models.trip_users.c.trip_id,
            func.count(models.trip_users.c.user_id),
        )
        .filter(models.trip_users.c.trip_id.in_(trip_ids))
        .group_by(models.trip_users.c.trip_id)
        .all()
    )

    stats = {row.trip_id: row for row in stats_rows}
    participant_counts = {trip_id: count for trip_id, count in participant_rows}

    for trip in trips:
        row = stats.get(trip.id)
        trip.total_items = row.total_items if row else 0
        trip.packed_items = row.packed_items if row else 0
        trip.participants_count = participant_counts.get(trip.id, 0)

    return {"items": trips, "total": total, "limit": limit, "offset": offset}

@router.get("/{trip_id}", response_model=schemas.TripDetailResponse)
@limiter.limit("100/minute")
def get_trip(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
):
    trip.total_items, trip.packed_items = _stats_for_trip(db, trip_id)
    return trip

@router.post("/{trip_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_trip(
    trip_id: int,
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    trip: models.Trip = Depends(get_accessible_trip)
):
    existing_cat = db.query(models.Category).filter(
        models.Category.name == category.name,
        models.Category.trip_id == trip_id
    ).first()
    if existing_cat:
        raise HTTPException(status_code=400, detail="Така категорія вже існує в цій поїздці")
        
    new_cat = models.Category(name=category.name, trip_id=trip_id, created_by_id=current_user.id)
    db.add(new_cat)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Така категорія вже існує в цій поїздці")
    db.refresh(new_cat)
    return new_cat

@router.patch("/{trip_id}", response_model=schemas.TripDetailResponse)
def update_trip(
    trip_id: int,
    trip_update: schemas.TripUpdate,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_owned_trip)
):
    if trip_update.title is not None:
        trip.title = trip_update.title

    db.commit()
    db.refresh(trip)
    trip.total_items, trip.packed_items = _stats_for_trip(db, trip_id)
    return trip

@router.get("/{trip_id}/categories/", response_model=List[schemas.CategoryResponse])
@limiter.limit("100/minute")
def get_categories_for_trip(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip)
):
    return db.query(models.Category).options(selectinload(models.Category.created_by)).filter(models.Category.trip_id == trip.id).all()

@router.get("/{trip_id}/items/", response_model=schemas.ItemListResponse)
@limiter.limit("100/minute")
def get_trip_items(
    request: Request,
    trip_id: int,
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_accessible_trip),
    q: Optional[str] = Query(default=None, max_length=100),
    category_id: Optional[int] = Query(default=None),
    assignee_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query_text = q.strip() if q else ""
    base = db.query(models.Item).filter(models.Item.trip_id == trip_id)

    if query_text:
        escaped = query_text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        base = base.filter(models.Item.name.ilike(f"%{escaped}%", escape="\\"))

    if category_id is not None:
        base = base.filter(models.Item.category_id == category_id)

    if assignee_id is not None:
        base = base.filter(models.Item.assigned_users.any(models.User.id == assignee_id))

    total = base.count()

    items = (
        base.options(*_ITEM_LOAD_OPTIONS)
        .order_by(case((models.Item.is_critical, 0), else_=1), models.Item.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {"items": items, "total": total, "limit": limit, "offset": offset}

@router.patch("/{trip_id}/categories/{category_id}", response_model=schemas.CategoryResponse)
def update_categories_for_trip(
    trip_id: int,
    category_id: int,
    category_update: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")

    if trip.owner_id != current_user.id:
        if not user_is_member(db, trip, current_user.id):
            raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")
        if category.created_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ви можете видаляти лише власні речі (створені вами)")

    if category.trip_id != trip_id:
        raise HTTPException(status_code=400, detail="Ця категорія не належить вказаній поїздці")

    category_exist = db.query(models.Category).filter(
        models.Category.name == category_update.name,
        models.Category.trip_id == trip_id,
        models.Category.id != category_id
    ).first()
    if category_exist:
        raise HTTPException(status_code=400, detail="Така категорія вже існує в цій поїздці")

    category.name = category_update.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Така категорія вже існує в цій поїздці")
    db.refresh(category)
    return category

@router.delete("/{trip_id}/categories/{category_id}")
def delete_category(
    trip_id: int,
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")

    if trip.owner_id != current_user.id:
        if not user_is_member(db, trip, current_user.id):
            raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")
        if category.created_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ви можете видаляти лише власні речі (створені вами)")

    if category.trip_id != trip_id:
        raise HTTPException(status_code=400, detail="Ця категорія не належить вказаній поїздці")

    category_name = category.name
    items_moved = db.query(models.Item).filter(models.Item.category_id == category.id).count()

    db.query(models.Item).filter(models.Item.category_id == category.id).update(
        {models.Item.category_id: None}
    )
    try:
        db.delete(category)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Категорію неможливо видалити, спробуйте ще раз")

    if items_moved:
        return {"message": f"Категорію '{category_name}' видалено. Речей перенесено до «Інше»: {items_moved}"}
    return {"message": f"Категорію '{category_name}' видалено"}

@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int, 
    db: Session = Depends(get_db),
    trip: models.Trip = Depends(get_owned_trip)
):
    db.delete(trip)
    db.commit()
    
    return {"message": "Поїздку успішно видалено"}
