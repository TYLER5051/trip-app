from sqlalchemy.orm import Session
from typing import Optional
import models
import json

def log_activity(
    db: Session,
    trip_id: int,
    actor_id: Optional[int],
    action: str,
    details: Optional[dict] = None,
    item_id: Optional[int] = None,
    category_id: Optional[int] = None
):
    json_details = json.dumps(details, ensure_ascii=False) if details is not None else None

    act = models.Activity(
        trip_id=trip_id,
        user_id=actor_id,
        action=action,
        details=json_details,
        item_id=item_id,
        category_id=category_id
    )

    db.add(act)