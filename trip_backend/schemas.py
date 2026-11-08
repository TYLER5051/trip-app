from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    model_config = ConfigDict(str_strip_whitespace=True)

class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=100)

class UserResponse(UserBase):
    id: int
    avatar_color: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserMeResponse(BaseModel):
    id: int
    username: str
    avatar_color: Optional[str] = None
    owned_trips_count: int
    participating_trips_count: int
    assigned_items_count: int
    total_items_count: int
    packed_items_count: int

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=30, pattern=r"^[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_-]+$")
    avatar_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    current_password: Optional[str] = Field(default=None)
    model_config = ConfigDict(str_strip_whitespace=True)

class CategoryBase(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    model_config = ConfigDict(str_strip_whitespace=True)

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
    model_config = ConfigDict(str_strip_whitespace=True)
    
class ItemCreate(ItemBase):
    trip_id: int
    category_id: int

class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    quantity: Optional[int] = Field(default=None, ge=1)
    note: Optional[str] = Field(default=None, max_length=200)
    is_critical: Optional[bool] = None
    category_id: Optional[int] = Field(default=None, description="Нова категорія; null = не міняти")
    model_config = ConfigDict(str_strip_whitespace=True)

class ItemResponse(ItemBase):
    id: int
    category_id: Optional[int] = None
    category: Optional[CategoryResponse] = None
    assigned_users: List[UserResponse] = Field(default_factory=list)
    created_by: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

class ItemListResponse(BaseModel):
    items: List[ItemResponse]
    total: int
    limit: int
    offset: int

class TripBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    model_config = ConfigDict(str_strip_whitespace=True)

class TripCreate(TripBase):
    pass

class TripUpdate(TripBase):
    title: Optional[str] = None
    model_config = ConfigDict(str_strip_whitespace=True)

class TripDetailResponse(TripBase):
    id: int
    owner: UserResponse
    participants: List[UserResponse] = Field(default_factory=list)
    total_items: int = 0
    packed_items: int = 0
    model_config = ConfigDict(from_attributes=True)

class TripSummaryResponse(TripBase):
    id: int
    owner: UserResponse
    participants_count: int = 0
    total_items: int = 0
    packed_items: int = 0
    model_config = ConfigDict(from_attributes=True)

class TripListResponse(BaseModel):
    items: List[TripSummaryResponse]
    total: int
    limit: int
    offset: int 

class InviteTokenResponse(BaseModel):
    invite_token: str

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=100)

class TransferOwnerRequest(BaseModel):
    new_owner_id: int