from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---- Auth ----

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=4, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- Groups ----

SUPPORTED_CURRENCIES = ("RUB", "USD", "EUR", "GBP", "KZT")


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    currency: str = Field(default="RUB")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {SUPPORTED_CURRENCIES}")
        return v


class GroupJoin(BaseModel):
    invite_code: str


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    currency: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        if v is not None and v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {SUPPORTED_CURRENCIES}")
        return v


class GroupOut(BaseModel):
    id: int
    name: str
    invite_code: str
    currency: str
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class GroupMemberOut(BaseModel):
    user_id: int
    username: str

    class Config:
        from_attributes = True


class GroupDetailOut(GroupOut):
    members: list[GroupMemberOut]


# ---- Expenses ----

class ExpenseParticipant(BaseModel):
    user_id: int
    share_amount: Optional[float] = None  # required when split_type == "custom"


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=256)
    amount: float = Field(gt=0)
    paid_by_id: int
    split_type: str = Field(default="equal")  # "equal" | "custom"
    participants: list[ExpenseParticipant]

    @field_validator("split_type")
    @classmethod
    def validate_split_type(cls, v):
        if v not in ("equal", "custom"):
            raise ValueError("split_type must be 'equal' or 'custom'")
        return v


class ExpenseShareOut(BaseModel):
    user_id: int
    username: str
    share_amount: float

    class Config:
        from_attributes = True


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    description: str
    amount: float
    paid_by_id: int
    paid_by_username: str
    created_by_id: int
    created_at: datetime
    shares: list[ExpenseShareOut]

    class Config:
        from_attributes = True


class BalanceOut(BaseModel):
    user_id: int
    username: str
    balance: float  # positive = is owed money, negative = owes money


class DebtOut(BaseModel):
    from_user_id: int
    from_username: str
    to_user_id: int
    to_username: str
    amount: float


class GroupBalancesOut(BaseModel):
    balances: list[BalanceOut]
    debts: list[DebtOut]


# ---- Analytics ----

class MonthlyStat(BaseModel):
    month: str  # "YYYY-MM"
    group_total: float
    my_total: float


class GroupAnalyticsOut(BaseModel):
    currency: str
    months: list[MonthlyStat]
