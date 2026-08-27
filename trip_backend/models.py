from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from database import Base

trip_users = Table(
    "trip_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("trip_id", Integer, ForeignKey("trips.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    owned_trips = relationship("Trip", back_populates="owner")
    participating_trips = relationship("Trip", secondary=trip_users, back_populates="participants")
    items_to_bring = relationship("Item", back_populates="assigned_user")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="owned_trips")
    participants = relationship("User", secondary=trip_users, back_populates="participating_trips")
    items = relationship("Item", back_populates="trip", cascade="all, delete")
    categories = relationship("Category", back_populates="trip", cascade="all, delete")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))

    items = relationship("Item", back_populates="category")
    trip = relationship("Trip", back_populates="categories")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) 
    is_packed = Column(Boolean, default=False) 

    trip_id = Column(Integer, ForeignKey("trips.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    trip = relationship("Trip", back_populates="items")
    category = relationship("Category", back_populates="items")
    assigned_user = relationship("User", back_populates="items_to_bring")