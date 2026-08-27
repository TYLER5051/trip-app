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
    model_config = ConfigDict(from_attributes=True)


class ItemBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    is_packed: bool = False

class ItemCreate(ItemBase):
    trip_id: int
    category_id: int  

class ItemUpdate(ItemBase):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    is_packed: Optional[bool] = None
    assigned_user_id: Optional[int] = None  

class ItemResponse(ItemBase):
    id: int
    category: CategoryResponse 
    assigned_user: Optional[UserResponse] = None  
    model_config = ConfigDict(from_attributes=True)


class TripBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)

class TripCreate(TripBase):
    pass

class TripResponse(TripBase):
    id: int
    owner: UserResponse  
    participants: List[UserResponse] = []  
    items: List[ItemResponse] = [] 
    model_config = ConfigDict(from_attributes=True)