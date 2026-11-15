from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload
from database import get_db
from deps import get_current_user, get_accessible_trip
from rate_limit import limiter
import models, schemas

router = APIRouter()

def _fetch_activities(db: Session, base_query, limit: int, offset: int):
    total = base_query.count()
    activities = (
        base_query.options(
            selectinload(models.Activity.actor),
            selectinload(models.Activity.trip)
        )
        .order_by(
            models.Activity.created_at.desc(),
            models.Activity.id.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"items": activities, "total": total, "limit": limit, "offset": offset}

@router.get("/trips/{trip_id}/activities", response_model=schemas.ActivityListResponse)
@limiter.limit("100/minute")
def get_activity(
    request: Request,
    trip_id: int,
    trip: models.Trip = Depends(get_accessible_trip),
    db: Session = Depends(get_db),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    base_query = db.query(models.Activity).filter(models.Activity.trip_id == trip.id)
    return _fetch_activities(db, base_query, limit, offset)

@router.get("/users/me/activities", response_model=schemas.ActivityListResponse)
@limiter.limit("100/minute")
def get_user_activity(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    base_query = (
        db.query(models.Activity)
        .join(models.Trip, models.Activity.trip_id == models.Trip.id)
        .filter(or_(
            models.Trip.owner_id == current_user.id,
            models.Trip.participants.any(models.User.id == current_user.id)
        ))
    )
    return _fetch_activities(db, base_query, limit, offset)