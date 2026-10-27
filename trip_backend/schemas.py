from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=30)

class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=100)

class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    name: str = Field(min_length=2, max_length=50)

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    trip_id: int
    created_by: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)

class CategoryUpdate(CategoryBase):
    pass

class ItemBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    quantity: int = Field(default=1, ge=1)
    note: Optional[str] = Field(default=None, max_length=200)
    is_critical: bool = False

class ItemCreate(ItemBase):
    trip_id: int
    category_id: int

class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    quantity: Optional[int] = Field(default=None, ge=1)
    note: Optional[str] = Field(default=None, max_length=200)
    is_critical: Optional[bool] = None
    category_id: Optional[int] = Field(default=None, description="Нова категорія; null = не міняти")

class ItemResponse(ItemBase):
    id: int
    category_id: Optional[int] = None
    category: Optional[CategoryResponse] = None
    assigned_users: List[UserResponse] = Field(default_factory=list)
    created_by: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)

class TripBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)

class TripCreate(TripBase):
    pass

class TripUpdate(TripBase):
    title: Optional[str] = None

class TripResponse(TripBase):
    id: int
    owner: UserResponse
    participants: List[UserResponse] = Field(default_factory=list)
    items: List[ItemResponse] = Field(default_factory=list)
    total_items: int = 0
    packed_items: int = 0
    model_config = ConfigDict(from_attributes=True)