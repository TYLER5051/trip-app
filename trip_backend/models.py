from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Table, UniqueConstraint, Index, CheckConstraint, Numeric, text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone

trip_users = Table(
    "trip_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("trip_id", Integer, ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True, index=True)
)

item_assignments = Table(
    "item_assignments",
    Base.metadata,
    Column("item_id", Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, index=True),
    Column("quantity", Integer, nullable=False, default=1, server_default="1"),
    CheckConstraint("quantity >= 1", name="ck_item_assignments_quantity_gte_1")
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    token_version = Column(Integer, default=1, nullable=False)
    avatar_color = Column(String, default=None)

    owned_trips = relationship("Trip", back_populates="owner")
    participating_trips = relationship("Trip", secondary=trip_users, back_populates="participants")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    invite_token = Column(String, unique=True, index=True, nullable=False)
    invite_expires_at = Column(DateTime(timezone=True), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)

    owner = relationship("User", back_populates="owned_trips")
    participants = relationship("User", secondary=trip_users, back_populates="participating_trips")
    items = relationship("Item", back_populates="trip", cascade="all, delete", passive_deletes=True)
    categories = relationship("Category", back_populates="trip", cascade="all, delete", passive_deletes=True)
    contributions = relationship("Contribution", back_populates="trip", cascade="all, delete", passive_deletes=True)
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete", passive_deletes=True)

class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("trip_id", "name", name="uq_categories_trip_name"),)
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    items = relationship("Item", back_populates="category")
    trip = relationship("Trip", back_populates="categories")
    created_by = relationship("User", foreign_keys=[created_by_id])


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("trip_id", "name", name="uq_items_trip_name"),
        CheckConstraint("quantity >= 1", name="ck_items_quantity_gte_1")
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) 
    quantity = Column(Integer, nullable=False, default=1)
    note = Column(String, nullable=True)
    is_critical = Column(Boolean, default=False)

    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)
    
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    trip = relationship("Trip", back_populates="items")
    category = relationship("Category", back_populates="items")
    created_by = relationship("User", foreign_keys=[created_by_id])
    assignments = relationship("ItemAssignment", back_populates="item", order_by="ItemAssignment.user_id", cascade="all, delete-orphan", passive_deletes=True)

class ItemAssignment(Base):
    __table__ = item_assignments

    user = relationship("User")
    item = relationship("Item", back_populates="assignments")

class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_trip_created", "trip_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String, nullable=False)
    details = Column(String, nullable=True)
    item_id  = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"))
    category_id  = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), index=True)

    trip = relationship("Trip")
    actor = relationship("User")

class Contribution(Base):
    __tablename__ = "contributions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_contributions_amount_positive"),
        Index("ix_contributions_trip_created", "trip_id", "created_at")    
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    note = Column(String(length=200), nullable=True,)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trip = relationship("Trip", back_populates="contributions")
    user = relationship("User", foreign_keys=[user_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        Index("ix_expenses_trip_created", "trip_id", "created_at")
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(length=100), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    paid_from_pool = Column(Boolean, nullable=False, default=True)
    paid_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(String(length=200), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    shares = relationship("ExpenseShare", back_populates="expense", cascade="all, delete-orphan", passive_deletes=True)
    trip = relationship("Trip", back_populates="expenses")
    paid_by_user = relationship("User", foreign_keys=[paid_by_user_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expense_shares_amount_positive"),
        Index("ix_expense_shares_expense_user", "expense_id", "user_id", unique=True, postgresql_where=text("user_id IS NOT NULL"))
    )

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    expense = relationship("Expense", back_populates="shares")
    user = relationship("User")