from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from deps import get_current_user
from rate_limit import limiter
import auth, models, schemas

PASSWORD_FOR_TIMING = auth.pwd_context.hash("dummy-password-for-timing")

router = APIRouter()

@router.post("/register", response_model=schemas.UserResponse)
@limiter.limit("5/minute")
def register_user(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password)
    try:
        db.add(new_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Некоректні дані або користувач вже існує")
    db.refresh(new_user)
    return new_user

@router.post("/login")
@limiter.limit("10/minute")
def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()

    if user is None or not auth.verify_password(form_data.password, user.hashed_password):
        auth.pwd_context.verify(form_data.password, PASSWORD_FOR_TIMING)
        raise HTTPException(status_code=401, detail="Неправильний логін або пароль")

    access_token = auth.create_access_token(data={"sub": str(user.id), "ver": user.token_version})
    return {"username": user.username, "access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
@limiter.limit("30/minute")
def logout_user(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.token_version += 1
    db.commit()

    return {"detail": "Ви успішно вийшли"}