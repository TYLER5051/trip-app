from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import List, Optional
from decimal import Decimal
import datetime
import json

class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_-]+$")
    model_config = ConfigDict(str_strip_whitespace=True)

class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)

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
    quantity: int = Field(default=1, ge=1, le=1000)
    note: Optional[str] = Field(default=None, max_length=200)
    is_critical: bool = False
    model_config = ConfigDict(str_strip_whitespace=True)
    
class ItemCreate(ItemBase):
    trip_id: int
    category_id: int

class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    quantity: Optional[int] = Field(default=None, ge=1, le=1000)
    note: Optional[str] = Field(default=None, max_length=200)
    is_critical: Optional[bool] = None
    category_id: Optional[int] = Field(default=None, description="Нова категорія; null = не міняти")
    model_config = ConfigDict(str_strip_whitespace=True)

class ItemAssignmentResponse(BaseModel):
    user: UserResponse
    quantity: int = Field(default=1, ge=1, le=1000)
    model_config = ConfigDict(from_attributes=True)

class AssignItemRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=1000)

class ItemResponse(ItemBase):
    id: int
    category_id: Optional[int] = None
    category: Optional[CategoryResponse] = None
    assignments: List[ItemAssignmentResponse] = Field(default_factory=list)
    created_by: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

class ItemListResponse(BaseModel):
    items: List[ItemResponse]
    total: int
    limit: int
    offset: int

class CopyItemRequest(BaseModel):
    source_trip_id: int

class CopyItemResponse(BaseModel):
    copied_items: int
    skipped_items: int
    message: str

class TripBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def check_date(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("Дата початку не може бути пізнішою за дату завершення")
        return self

class TripCreate(TripBase):
    pass

class TripUpdate(TripBase):
    title: Optional[str] = Field(default=None, min_length=3, max_length=100)
    model_config = ConfigDict(str_strip_whitespace=True)

class TripDetailResponse(TripBase):
    id: int
    owner: UserResponse
    participants: List[UserResponse] = Field(default_factory=list)
    total_items: int = 0
    packed_items: int = 0
    is_archived: bool = False
    model_config = ConfigDict(from_attributes=True)

class TripSummaryResponse(TripBase):
    id: int
    owner: UserResponse
    participants_count: int = 0
    total_items: int = 0
    packed_items: int = 0
    is_archived: bool = False
    model_config = ConfigDict(from_attributes=True)

class TripListResponse(BaseModel):
    items: List[TripSummaryResponse]
    total: int
    limit: int
    offset: int 

class TripShortResponse(BaseModel):
    id: int
    title: str
    model_config = ConfigDict(from_attributes=True)

class AssignedItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    note: Optional[str] = None
    is_critical: bool = False
    trip: TripShortResponse
    category: Optional[CategoryResponse] = None
    assignments: List[ItemAssignmentResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class AssignedItemsListResponse(BaseModel):
    items: List[AssignedItemResponse]
    total: int
    model_config = ConfigDict(from_attributes=True)

class InviteTokenResponse(BaseModel):
    invite_token: str

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)

class TransferOwnerRequest(BaseModel):
    new_owner_id: int

class DeleteAccountRequest(BaseModel):
    current_password: str

class ActivityResponse(BaseModel):
    id: int
    action: str
    actor: Optional[UserResponse]
    trip_id: int
    trip: TripShortResponse
    item_id: Optional[int]
    category_id: Optional[int]
    details: Optional[dict] = None
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("details", mode="before")
    @classmethod
    def to_json(cls, d):
        if isinstance(d, str):
            try:
                return json.loads(d)
            except (json.JSONDecodeError, TypeError):
                return None
        return d
    
class ActivityListResponse(BaseModel):
    items: List[ActivityResponse]
    total: int
    limit: int
    offset: int

class ContributionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=200)

class ContributionUpdate(BaseModel):
    amount: Optional[Decimal] = Field(gt=0, max_digits=12, decimal_places=2)
    note: Optional[str] = Field(default=None, max_length=200)

class ContributionResponse(BaseModel):
    id: int
    user: UserResponse | None
    amount: Decimal
    note: str | None
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class ExpenseShareRequest(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

class ExpenseShareResponse(BaseModel):
    user: UserResponse | None
    amount: Decimal

class ExpenseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    paid_from_pool: bool = True
    paid_by_user_id: int | None = None
    shares: list[ExpenseShareRequest] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def check_model(self):
        user_ids = [s.user_id for s in self.shares]
        if len(set(user_ids)) < len(user_ids):
            raise ValueError("Користувачі у частках мають бути унікальними")
        if sum((s.amount for s in self.shares), Decimal("0.00")) != self.amount:
            raise ValueError("Сума часток має дорівнювати загальній сумі витрати")
        if self.paid_from_pool is False and self.paid_by_user_id is None:
            raise ValueError("Для особистої оплати потрібно вказати платника")
        return self
    
class ExpenseUpdate(BaseModel):
    name: Optional[str] = Field(min_length=2, max_length=100, default=None)
    amount: Optional[Decimal] = Field(gt=0, max_digits=12, decimal_places=2, default=None)
    paid_from_pool: Optional[bool] = None
    paid_by_user_id: Optional[int] = None
    shares: Optional[list[ExpenseShareRequest]] = Field(min_length=1, default=None)
    note: Optional[str] = Field(default=None, max_length=200)
    
    @model_validator(mode="after")
    def check_model(self):
        if self.shares is not None:
            user_ids = [s.user_id for s in self.shares]
            if len(set(user_ids)) < len(user_ids):
                raise ValueError("Користувачі у частках мають бути унікальними")
            if self.amount is not None and sum((s.amount for s in self.shares), Decimal("0.00")) != self.amount:
                raise ValueError("Сума часток має дорівнювати загальній сумі витрати")
        if self.paid_from_pool is False and self.paid_by_user_id is None:
            raise ValueError("Для особистої оплати потрібно вказати платника")
        return self

class ExpenseResponse(BaseModel):
    id: int
    name: str
    amount: Decimal
    paid_from_pool: bool
    paid_by_user: UserResponse | None
    shares: list[ExpenseShareResponse]
    note: str | None
    created_at: datetime.datetime
    created_by: UserResponse | None
    model_config = ConfigDict(from_attributes=True)

class ParticipantBalance(BaseModel):
    user: UserResponse | None
    contributed: Decimal
    paid_by_self: Decimal
    share_costs: Decimal
    net: Decimal

class DeleteUsersSummary(BaseModel):
    contributed: Decimal
    share_costs: Decimal
    net: Decimal

class BudgetOverviewResponse(BaseModel):
    bank_balance: Decimal
    total_contributions: Decimal
    total_expenses: Decimal
    participants: list[ParticipantBalance]
    deleted_users: DeleteUsersSummary

class SettlementTransfer(BaseModel):
    from_user: UserResponse
    to_user: UserResponse
    amount: Decimal

class BankPayout(BaseModel):
    user: UserResponse
    amount: Decimal

class SettlementResponse(BaseModel):
    bank_balance: Decimal
    transfers: list[SettlementTransfer]
    bank_payouts: list[BankPayout]
    deleted_users_note: str | None = None