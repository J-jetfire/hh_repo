import datetime
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator
from pydantic.types import Decimal, PositiveInt

from app.schemas.ad import ItemsOutModel, LocationOutModel


class UserId(BaseModel):
    id: int

    class Config:
        orm_mode = True


class UserRegistration(BaseModel):
    name: str
    password: str
    agree: bool

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    name: str
    phone: str
    password: str = Field(regex=r"^[a-zA-Z](?=.*?[0-9]).{7,20}$")

    class Config:
        orm_mode = True


class UserChangePassword(BaseModel):
    current_password: str
    new_password: str
    token: str

    class Config:
        orm_mode = True


class UserChangePasswordValidation(BaseModel):
    current_password: str
    new_password: str = Field(regex=r"^[a-zA-Z](?=.*?[0-9]).{7,20}$")

    class Config:
        orm_mode = True


class UserPhoto(BaseModel):
    id: UUID | None = None
    user_id: int | None = None
    url: str | None = None

    class Config:
        orm_mode = True


class UserCreateOauth(BaseModel):
    email: str | None = None
    name: str | None = None
    surname: str | None = None
    password: str | None = None
    emailVerify: bool = False
    photo: Optional[UserPhoto] | None = None
    googleId: str | None = None
    vkId: str | None = None
    appleId: str | None = None

    class Config:
        orm_mode = True


class UserChange(BaseModel):
    email: str | None = None
    name: str | None = None

    class Config:
        orm_mode = True


class UserDevicesCreate(BaseModel):
    os: str
    brand: str
    deviceId: str
    model: str
    manufacturer: str
    fingerprint: str
    ip: str
    userAgent: str
    uniqueId: str

    class Config:
        orm_mode = True


class UserDevicesOut(BaseModel):
    id: int
    model: str | None = None
    os: str | None = None
    brand: str | None = None
    deviceId: str | None = None
    manufacturer: str | None = None
    fingerprint: str | None = None
    ip: str | None = None
    userAgent: str | None = None
    uniqueId: str | None = None

    class Config:
        orm_mode = True


class UserOut(BaseModel):
    id: int
    email: str | None = None
    emailVerified: bool
    phone: str | None = None
    phoneVerified: bool
    name: str | None = None
    rating: float | None = None
    feedback_count: int | None = None
    photo: UUID | None = None

    googleId: str | None = None
    appleId: str | None = None

    is_active: bool
    is_blocked: bool

    createdAt: datetime.datetime
    updatedAt: datetime.datetime | None = None
    lastLoginAt: datetime.datetime | None = None

    class Config:
        orm_mode = True

    @validator("photo", pre=True)
    def format_photo(cls, value, **kwargs):
        if value is not None:
            return value.id
        return None


class UserMiniCardOut(BaseModel):
    id: int
    name: str | None = None
    rating: float | None = None
    feedback_count: int | None = None
    subscriptions_count: int | None = None
    subscribers_count: int | None = None
    photo: UUID | None = None
    online: bool
    online_at: datetime.datetime | None = None

    is_active: bool
    is_blocked: bool

    createdAt: datetime.datetime

    class Config:
        orm_mode = True

    @validator("photo", pre=True)
    def format_photo(cls, value, **kwargs):
        if value is not None:
            return value.id
        return None


class UserOutMe(BaseModel):
    id: int
    email: str | None = None
    emailVerified: bool
    phone: str | None = None
    phoneVerified: bool
    name: str | None = None
    rating: float | None = None
    balance: int | None = None
    unread_messages: int | None = None
    feedback_count: int | None = None
    subscriptions_count: int | None = None
    subscribers_count: int | None = None
    photo: UUID | None = None
    location: Optional[LocationOutModel] | dict = None

    googleId: str | None = None
    appleId: str | None = None

    is_active: bool
    is_blocked: bool

    createdAt: datetime.datetime
    updatedAt: datetime.datetime | None = None
    lastLoginAt: datetime.datetime | None = None

    class Config:
        orm_mode = True

    @validator("photo", pre=True)
    def format_photo(cls, value, **kwargs):
        if value is not None:
            return value.id
        return None


class UserAdvsOut(BaseModel):
    active: List[ItemsOutModel]
    completed: List[ItemsOutModel]


class UserCardOut(BaseModel):
    id: int
    name: str | None = None
    photo: UUID | None = None
    float: int | None = None
    feedbacks: int | None = None
    subscriptions: int | None = None
    subscribers: int | None = None
    is_active: bool
    advs: UserAdvsOut

    class Config:
        orm_mode = True

    @validator("photo", pre=True)
    def format_photo(cls, value, **kwargs):
        return value.id


class UserChangePhone(BaseModel):
    new_phone: str
    old_phone: str

    class Config:
        orm_mode = True


class ListAdvsOut(BaseModel):
    ad_list: List[UUID]
    page: int = 1
    limit: int = 50


class DepositOrWithdrawModel(BaseModel):
    amount: Union[int, float]
    service: str = None
    service_id: str = None

    @validator('amount')
    def check_amount(cls, value):
        # Проверка, что значение не отрицательное
        if value <= 0:
            raise ValueError('Amount must be more than 0')

        # Если значение - целое число, оставляем его так
        if isinstance(value, int):
            return value

        # Если значение - не целое число, обрезаем десятичную часть
        if isinstance(value, float):
            return int(value)

        # Если значение не целое число и не число с плавающей точкой, возбуждаем исключение
        raise ValueError('Invalid amount')


class CashWalletOut(BaseModel):
    id: UUID
    user_id: int
    balance: int


class WalletTransactions(BaseModel):
    id: str
    cash: PositiveInt
    deposit: PositiveInt
    cash_sign: bool
    service: str
    created_at: str


class TransactionsResponse(BaseModel):
    total: int
    transactions: List[WalletTransactions]


# class WalletTransactionOut(BaseModel):
#     id: UUID
#     user_id: int
#     cash_wallet_id: UUID
#     transaction_type: str
#     cash: int
#     cash_sign: str
#     service: str
#     created_at: str
#
#
# class PaginatedTransactions(BaseModel):
#     total: int
#     transactions: List[WalletTransactionOut]
