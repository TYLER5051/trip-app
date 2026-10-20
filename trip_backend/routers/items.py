from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from routers.authentication import get_current_user
import models, schemas

router = APIRouter(prefix="/items")

@router.post("/", response_model=schemas.ItemResponse)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == item.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    category = db.query(models.Category).filter(models.Category.id == item.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db_item = models.Item(
        name=item.name, 
        is_packed=False, 
        trip_id=item.trip_id, 
        category_id=item.category_id
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
    if not item:
        raise HTTPException(status_code=404, detail="Річ не знайдено")
        
    trip = db.get(models.Trip, item.trip_id)
    
    if item.assigned_user_id is not None:
        if current_user.id != item.assigned_user_id and current_user.id != trip.owner.id:
            raise HTTPException(
                status_code=403, 
                detail="Ви не можете зняти галочку з чужої речі!"
            )
            
    if item_update.name is not None:
        item.name = item_update.name
        
    if item_update.is_packed is False:
        item.assigned_user_id = None
        item.is_packed = False
    elif item_update.is_packed is True:
        item.assigned_user_id = current_user.id
        item.is_packed = True
        
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": f"Item '{item.name}' deleted"}