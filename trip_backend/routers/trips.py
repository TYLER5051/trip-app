from fastapi import APIRouter, Depends, HTTPException, status
from routers.authentication import get_current_user
from sqlalchemy.orm import Session
from database import get_db
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
    return list(set(trips))

@router.get("/{trip_id}", response_model=schemas.TripResponse)
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

@router.post("/{trip_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_trip(
    trip_id: int,
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if not trip_db:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
        
    # Перевіряємо, чи немає вже такої категорії САМЕ В ЦІЙ поїздці
    existing_cat = db.query(models.Category).filter(
        models.Category.name == category.name,
        models.Category.trip_id == trip_id
    ).first()
    if existing_cat:
        raise HTTPException(status_code=400, detail="Така категорія вже існує в цій поїздці")
        
    new_cat = models.Category(name=category.name, trip_id=trip_id)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@router.get("/{trip_id}/categories/", response_model=List[schemas.CategoryResponse])
def get_categories_for_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Повертаємо категорії ТІЛЬКИ для цієї поїздки
    return db.query(models.Category).filter(models.Category.trip_id == trip_id).all()

@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    
    if not trip_db:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    
    if trip_db.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Тільки організатор може видалити цю поїздку"
        )
    
    db.delete(trip_db)
    db.commit()
    
    return {"message": "Поїздку успішно видалено"}