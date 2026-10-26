from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
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

    existing_item = db.query(models.Item).filter(
        models.Item.trip_id == item.trip_id,
        models.Item.name == item.name
    ).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="Така річ вже існує в цій поїздці")

    db_item = models.Item(
        name=item.name,
        quantity=item.quantity,
        note=item.note,
        is_critical=item.is_critical,
        trip_id=trip.id,
        category_id=category.id,
        created_by_id=current_user.id
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

    # Зміна "змісту" речі (назва, кількість, примітка, критичність, категорія)
    # — тільки автор або організатор.
    content_changed = any(
        value is not None
        for value in (item_update.name, item_update.quantity, item_update.note,
                      item_update.is_critical, item_update.category_id)
    )
    if content_changed:
        if trip.owner_id != current_user.id and item.created_by_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Ви можете змінювати лише власні речі (створені вами)"
            )

        if item_update.name is not None or item_update.category_id is not None:
            effective_name = item_update.name if item_update.name is not None else item.name
            duplicate = db.query(models.Item).filter(
                models.Item.name == effective_name,
                models.Item.trip_id == item.trip_id,
                models.Item.id != item_id
            ).first()
            if duplicate:
                raise HTTPException(status_code=400, detail="Така річ вже існує в цій поїздці")

        if item_update.name is not None:
            item.name = item_update.name

        if item_update.quantity is not None:
            item.quantity = item_update.quantity

        if item_update.note is not None:
            item.note = item_update.note

        if item_update.is_critical is not None:
            item.is_critical = item_update.is_critical

        if item_update.category_id is not None:
            new_category = db.get(models.Category, item_update.category_id)
            if new_category is None:
                raise HTTPException(status_code=404, detail="Категорію не знайдено")
            if new_category.trip_id != trip.id:
                raise HTTPException(
                    status_code=400,
                    detail="Ця категорія належить іншій поїздці"
                )
            item.category_id = new_category.id

    db.commit()
    db.refresh(item)
    return item

@router.post("/{item_id}/assign", response_model=schemas.ItemResponse)
def assign_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    participant_ids = [p.id for p in trip.participants]
    if trip.owner_id != current_user.id and current_user.id not in participant_ids:
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    if current_user in item.assigned_users:
        raise HTTPException(status_code=400, detail="Ви вже взяли цю річ")

    if len(item.assigned_users) >= item.quantity:
        raise HTTPException(status_code=400, detail="Цю річ уже розібрали — кількість вичерпана")

    item.assigned_users.append(current_user)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}/assign", response_model=schemas.ItemResponse)
def unassign_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    participant_ids = [p.id for p in trip.participants]
    if trip.owner_id != current_user.id and current_user.id not in participant_ids:
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    if current_user not in item.assigned_users:
        raise HTTPException(status_code=400, detail="Ви не брали цю річ")

    item.assigned_users.remove(current_user)
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

    if item.is_critical:
        raise HTTPException(
            status_code=400,
            detail="Важливу річ неможливо видалити. Спочатку зніміть мітку «Важлива» (це може зробити автор або організатор)."
        )

    if trip.owner_id != current_user.id and item.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете видаляти лише власні речі (створені вами)")
    
    db.delete(item)
    db.commit()
    return {"message": f"Річ '{item.name}' видалена"}
