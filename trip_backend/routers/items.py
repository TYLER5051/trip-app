from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from deps import get_current_user
import models, schemas

router = APIRouter(prefix="/items")

@router.post("/", response_model=schemas.ItemResponse)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    participant_ids = [p.id for p in trip.participants]
    if trip.owner_id != current_user.id and current_user.id not in participant_ids:
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    category = db.get(models.Category, item.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категорію не знайдено")

    if category.trip_id != trip.id:
        raise HTTPException(
            status_code=400,
            detail="Ця категорія належить іншій поїздці"
        )

    db_item = models.Item(
        name=item.name,
        is_packed=False,
        trip_id=trip.id,
        category_id=category.id
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.patch("/{item_id}", response_model=schemas.ItemResponse)
def update_item(
    item_id: int,
    item_update: schemas.ItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    participant_ids = [p.id for p in trip.participants]
    if trip.owner_id != current_user.id and current_user.id not in participant_ids:
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    if item_update.name is not None:
        if trip.owner_id != current_user.id and item.assigned_user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Ви можете перейменовувати лише свої речі"
            )
        item.name = item_update.name

    if item_update.is_packed is False:
        if item.assigned_user_id is not None and current_user.id != item.assigned_user_id and current_user.id != trip.owner_id:
            raise HTTPException(
                status_code=403,
                detail="Ви не можете зняти галочку з чужої речі!"
            )
        item.assigned_user_id = None
        item.is_packed = False
    elif item_update.is_packed is True:
        if item.assigned_user_id is not None and current_user.id != item.assigned_user_id and current_user.id != trip.owner_id:
            raise HTTPException(
                status_code=403,
                detail="Цю річ уже взяв інший учасник"
            )
        item.assigned_user_id = current_user.id
        item.is_packed = True
        
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and item.assigned_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете видаляти лише свої речі")
    
    db.delete(item)
    db.commit()
    return {"message": f"Річ '{item.name}' видалена"}
