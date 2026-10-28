from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from deps import get_current_user
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
    db.commit()
    return {"invite_token": trip.invite_token}


@router.post("/invite/{token}")
def join_by_invite_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.invite_token == token).first()
    if trip is None:
        raise HTTPException(status_code=404, detail="Інвайт-токен недійсний")

    if trip.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Ви вже є організатором цієї поїздки")

    if any(p.id == current_user.id for p in trip.participants):
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
    if trip is None:
        raise HTTPException(status_code=404, detail="Інвайт-токен недійсний")

    return {
        "id": trip.id,
        "title": trip.title,
        "owner": {"username": trip.owner.username} if trip.owner else None,
        "participants_count": len(trip.participants),
        "items_count": len(trip.items)
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
    if not user_to_remove or user_to_remove not in trip_db.participants:
        raise HTTPException(status_code=404, detail="Учасника не знайдено в цій поїздці")
    
    trip_db.participants.remove(user_to_remove)
    
    for item in trip_db.items:
        if user_to_remove in item.assigned_users:
            item.assigned_users.remove(user_to_remove)
            
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
    
    if current_user not in trip_db.participants:
        raise HTTPException(status_code=400, detail="Ви не є учасником цієї поїздки")
        
    if trip_db.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Організатор не може вийти, він може лише видалити поїздку")
        
    trip_db.participants.remove(current_user)
    
    for item in trip_db.items:
        if current_user in item.assigned_users:
            item.assigned_users.remove(current_user)
            
    db.commit()
    
    return {"message": "Ви успішно вийшли з поїздки"}
