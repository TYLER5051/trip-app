from fastapi import status, FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, schemas
from database import engine, SessionLocal
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from typing import List
import auth

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Trip API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

@app.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/trips/", response_model=schemas.TripResponse)
def create_trip(
    trip: schemas.TripCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)):
    db_trip = models.Trip(title=trip.title, owner_id=current_user.id)

    db.add(db_trip)
    db.commit()
    db.refresh(db_trip)
    return db_trip

@app.get("/trips/", response_model=list[schemas.TripResponse])
def get_trips(current_user: models.User = Depends(get_current_user)):
    trips = current_user.owned_trips + current_user.participating_trips
    return list(set(trips))

@app.get("/trips/{trip_id}", response_model=schemas.TripResponse)
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.post("/trips/{trip_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_trip(
    trip_id: int,
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    if not trip_db:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
        
    # Перевіряємо, чи немає вже такої категорії САМЕ В ЦІЙ поїздці
    existing_cat = db.query(models.Category).filter(
        models.Category.name == category.name,
        models.Category.trip_id == trip_id
    ).first()
    if existing_cat:
        raise HTTPException(status_code=400, detail="Така категорія вже існує в цій поїздці")
        
    new_cat = models.Category(name=category.name, trip_id=trip_id)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@app.get("/trips/{trip_id}/categories/", response_model=List[schemas.CategoryResponse])
def get_categories_for_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Повертаємо категорії ТІЛЬКИ для цієї поїздки
    return db.query(models.Category).filter(models.Category.trip_id == trip_id).all()

@app.post("/items/", response_model=schemas.ItemResponse)
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

@app.post("/trips/{trip_id}/join", response_model=schemas.TripResponse)
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

@app.patch("/items/{item_id}", response_model=schemas.ItemResponse)
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

@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": f"Item '{item.name}' deleted"}

@app.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trip_db = db.get(models.Trip, trip_id)
    
    if not trip_db:
        raise HTTPException(status_code=404, detail="Поїздку не знайдено")
    
    if trip_db.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Тільки організатор може видалити цю поїздку"
        )
    
    db.delete(trip_db)
    db.commit()
    
    return {"message": "Поїздку успішно видалено"}

@app.delete("/trips/{trip_id}/participants/{user_id}")
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

@app.delete("/trips/{trip_id}/leave")
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