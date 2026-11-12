from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from database import get_db
from deps import get_current_user, user_is_member
import models, schemas

router = APIRouter(prefix="/items")

@router.post("/", response_model=schemas.ItemResponse)
def create_item(
    item: schemas.ItemCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and not user_is_member(db, trip, current_user.id):
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Така річ вже існує в цій поїздці")

    refreshed_item = (
    db.query(models.Item)
    .options(
        selectinload(models.Item.assignments).selectinload(models.ItemAssignment.user),
        selectinload(models.Item.created_by),
        selectinload(models.Item.category),
    )
    .filter(models.Item.id == db_item.id)
    .first()
    )

    return refreshed_item

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

    if trip.owner_id != current_user.id and not user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

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
            if item_update.quantity < sum(a.quantity for a in item.assignments):
                raise HTTPException(status_code=400, detail="Кількість не може бути меншою за кількість уже розібраних одиниць")
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Така річ вже існує в цій поїздці")

    refreshed_item = (
    db.query(models.Item)
    .options(
        selectinload(models.Item.assignments).selectinload(models.ItemAssignment.user),
        selectinload(models.Item.created_by),
        selectinload(models.Item.category),
    )
    .filter(models.Item.id == item_id)
    .first()
    )

    return refreshed_item

@router.post("/{item_id}/assign", response_model=schemas.ItemResponse)
def assign_item(
    item_id: int,
    assign_request: Optional[schemas.AssignItemRequest] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = db.query(models.Item).filter(models.Item.id == item_id).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and not user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    requested_quantity = assign_request.quantity if assign_request else 1

    current_total = (
        db.query(func.coalesce(func.sum(models.ItemAssignment.quantity), 0))
        .filter(models.ItemAssignment.item_id == item.id)
        .scalar()
    )

    assignment = (
        db.query(models.ItemAssignment)
        .filter(
            models.ItemAssignment.item_id == item.id,
            models.ItemAssignment.user_id == current_user.id,
        )
        .first()
    )
    existing_quantity = assignment.quantity if assignment else 0

    if current_total - existing_quantity + requested_quantity > item.quantity:
        raise HTTPException(status_code=400, detail="Цю річ уже розібрали — кількість вичерпана")

    if assignment is None:
        assignment = models.ItemAssignment(item_id=item.id, user_id=current_user.id)

    assignment.quantity = requested_quantity

    try:
        db.add(assignment)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ви вже взяли цю річ")

    refreshed_item = (
        db.query(models.Item)
        .options(
            selectinload(models.Item.assignments).selectinload(models.ItemAssignment.user),
            selectinload(models.Item.created_by),
            selectinload(models.Item.category),
        )
        .filter(models.Item.id == item_id)
        .first()
    )

    return refreshed_item

@router.delete("/{item_id}/assign", response_model=schemas.ItemResponse)
def unassign_item(
    item_id: int,
    user_id: Optional[int] = Query(default=None, description="ID користувача, у якого організатор знімає річ"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = db.query(models.Item).filter(models.Item.id == item_id).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Річ не знайдено")

    trip = db.get(models.Trip, item.trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")

    if trip.owner_id != current_user.id and not user_is_member(db, trip, current_user.id):
        raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")

    if user_id is not None:
        if trip.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Тільки організатор може знімати позначки інших учасників")
        target_user = db.get(models.User, user_id)
        if target_user is None:
            raise HTTPException(status_code=400, detail="Цей користувач не брав цю річ")
    else:
        target_user = current_user

    assignment = (
        db.query(models.ItemAssignment)
        .filter(
            models.ItemAssignment.item_id == item.id,
            models.ItemAssignment.user_id == target_user.id,
        )
        .first()
    )
    if assignment is None:
        if user_id is not None:
            raise HTTPException(status_code=400, detail="Цей користувач не брав цю річ")
        raise HTTPException(status_code=400, detail="Ви не брали цю річ")

    try:
        db.delete(assignment)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Не вдалося зняти позначку. Спробуйте ще раз")

    refreshed_item = (
        db.query(models.Item)
        .options(
            selectinload(models.Item.assignments).selectinload(models.ItemAssignment.user),
            selectinload(models.Item.created_by),
            selectinload(models.Item.category),
        )
        .filter(models.Item.id == item_id)
        .first()
    )

    return refreshed_item

@router.delete("/{item_id}")
def delete_item(
    item_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
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

    if trip.owner_id != current_user.id:
        if not user_is_member(db, trip, current_user.id):
            raise HTTPException(status_code=403, detail="Ви не є учасником цієї поїздки")
        if item.created_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="Ви можете видаляти лише власні речі (створені вами)")

    try:
        db.delete(item)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Річ видаляється іншим користувачем, спробуйте ще раз")
    
    return {"message": f"Річ '{item.name}' видалена"}
