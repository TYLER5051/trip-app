from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from deps import get_current_user
from typing import List
import models, schemas

router = APIRouter(prefix="/trips")

@router.post("/", response_model=schemas.TripResponse)
def create_trip(
    trip: schemas.TripCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_trip = models.Trip(title=trip.title, owner_id=current_user.id)

    db.add(db_trip)
    db.commit()
    db.refresh(db_trip)
    return db_trip

@router.get("/", response_model=list[schemas.TripResponse])
def get_trips(current_user: models.User = Depends(get_current_user)):
    trips = current_user.owned_trips + current_user.participating_trips
    return list(dict.fromkeys(trips))

@router.get("/{trip_id}", response_model=schemas.TripResponse)
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    
    return trip

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
    db.commit()
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
    return trip

@router.get("/{trip_id}/categories/", response_model=List[schemas.CategoryResponse])
def get_categories_for_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

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
    db.commit()
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
