from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
from database import get_db
from deps import get_current_user
from typing import List, Optional
import models, schemas
import secrets

router = APIRouter(prefix="/trips")

_TRIP_LOAD_OPTIONS = (
    selectinload(models.Trip.items).selectinload(models.Item.assigned_users),
    selectinload(models.Trip.items).selectinload(models.Item.created_by),
    selectinload(models.Trip.items).selectinload(models.Item.category)
        .selectinload(models.Category.created_by),
    selectinload(models.Trip.owner),
    selectinload(models.Trip.participants),
)

def _with_stats(trip):
    trip.total_items = len(trip.items)
    trip.packed_items = sum(1 for item in trip.items if item.assigned_users)
    return trip

@router.post("/", response_model=schemas.TripResponse)
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
    db.refresh(db_trip)
    return db_trip

@router.get("/", response_model=schemas.TripListResponse)
def get_trips(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    q: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)):

    query_text = q.strip() if q else ""
    base = db.query(models.Trip).filter(
        or_(
            models.Trip.owner_id == current_user.id,
            models.Trip.participants.any(models.User.id == current_user.id),
        )
    )

    if query_text:
        escaped = query_text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        base = base.filter(models.Trip.title.ilike(f"%{escaped}%", escape="\\"))

    total = base.count()
    
    trips = (
        base.options(
            selectinload(models.Trip.owner),
            selectinload(models.Trip.participants),
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

    stats = {row.trip_id: row for row in stats_rows}

    for trip in trips:
        row = stats.get(trip.id)
        trip.total_items = row.total_items if row else 0
        trip.packed_items = row.packed_items if row else 0

    return {"items": trips, "total": total, "limit": limit, "offset": offset}

@router.get("/{trip_id}", response_model=schemas.TripResponse)
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = (
        db.query(models.Trip)
        .options(*_TRIP_LOAD_OPTIONS)
        .filter(models.Trip.id == trip_id)
        .first()
    )
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and current_user.id not in [p.id for p in trip.participants]:
        raise HTTPException(status_code=403, detail="У вас немає доступу до цієї поїздки")

    return _with_stats(trip)

@router.post("/{trip_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_trip(
    trip_id: int,
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if trip_db is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    participant_ids = [p.id for p in trip_db.participants]
    if trip_db.owner_id != current_user.id and current_user.id not in participant_ids:
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

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

@router.patch("/{trip_id}", response_model=schemas.TripResponse)
def update_trip(
    trip_id: int,
    trip_update: schemas.TripUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Тільки організатор може змінювати назву")

    if trip_update.title is not None:
        trip.title = trip_update.title

    db.commit()
    db.refresh(trip)
    return _with_stats(trip)

@router.get("/{trip_id}/categories/", response_model=List[schemas.CategoryResponse])
def get_categories_for_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and current_user.id not in [p.id for p in trip.participants]:
        raise HTTPException(status_code=403, detail="У вас немає доступу до цієї поїздки")

    return db.query(models.Category).filter(models.Category.trip_id == trip.id).all()

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

    if category.trip_id != trip_id:
        raise HTTPException(status_code=400, detail="Ця категорія не належить вказаній поїздці")

    if trip.owner_id != current_user.id and category.created_by_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Ви можете змінювати лише власні категорії (створені вами)"
        )

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

    if category.trip_id != trip_id:
        raise HTTPException(status_code=400, detail="Ця категорія не належить вказаній поїздці")

    if trip.owner_id != current_user.id and category.created_by_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Ви можете видаляти лише власні категорії (створені вами)"
        )

    category_name = category.name
    items_moved = db.query(models.Item).filter(models.Item.category_id == category.id).count()

    db.query(models.Item).filter(models.Item.category_id == category.id).update(
        {models.Item.category_id: None}
    )
    db.delete(category)
    db.commit()

    if items_moved:
        return {"message": f"Категорію '{category_name}' видалено. Речей перенесено до «Інше»: {items_moved}"}
    return {"message": f"Категорію '{category_name}' видалено"}

@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if trip_db is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    
    if trip_db.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Тільки організатор може видалити цю поїздку")
    
    db.delete(trip_db)
    db.commit()
    
    return {"message": "Поїздку успішно видалено"}
