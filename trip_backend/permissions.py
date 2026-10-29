from sqlalchemy.orm import Session
import models


def user_is_member(db: Session, trip, user_id: int) -> bool:
    """Чи є user_id учасником trip — EXISTS по асоціативній таблиці,
    без завантаження всього списку participants у пам'ять."""
    return (
        db.query(models.trip_users.c.user_id)
        .filter(
            models.trip_users.c.trip_id == trip.id,
            models.trip_users.c.user_id == user_id,
        )
        .first()
        is not None
    )