from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.authentication import get_current_user
import models, schemas

router = APIRouter(prefix="/trips")

@router.post("/{trip_id}/join", response_model=schemas.TripResponse)
def join_trip(
    trip_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if current_user in trip.participants:
        raise HTTPException(status_code=400, detail="You are already a participant of this trip")
    
    if trip.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot join their own trip as a participant")

    trip.participants.append(current_user)
    db.commit()
    db.refresh(trip)
    
    return trip


@router.delete("/{trip_id}/participants/{user_id}")
def remove_participant(
    trip_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if not trip_db:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    
    if trip_db.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Тільки організатор може видаляти учасників"
        )
    
    user_to_remove = db.get(models.User, user_id)
    if not user_to_remove or user_to_remove not in trip_db.participants:
        raise HTTPException(status_code=404, detail="Учасника не знайдено в цій поїздці")
    
    trip_db.participants.remove(user_to_remove)
    
    for item in trip_db.items:
        if item.assigned_user_id == user_to_remove.id:
            item.assigned_user_id = None
            item.is_packed = False 
            
    db.commit()
    
    return {"message": "Учасника успішно видалено, а його речі звільнено"}


@router.delete("/{trip_id}/leave")
def leave_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if not trip_db:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    
    if current_user not in trip_db.participants:
        raise HTTPException(status_code=400, detail="Ви не є учасником цієї поїздки")
        
    if trip_db.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Організатор не може вийти, він може лише видалити поїздку")
        
    trip_db.participants.remove(current_user)
    
    for item in trip_db.items:
        if item.assigned_user_id == current_user.id:
            item.assigned_user_id = None
            
    db.commit()
    
    return {"message": "Ви успішно вийшли з поїздки"}