import datetime
from enum import Enum
from typing import Dict, Optional, Union, Any, List
from uuid import UUID

from pydantic import BaseModel

from app.schemas.catalog import CatalogSchemaAdditionalFields


class Location(BaseModel):
    address: str
    full_address: str
    detail: Dict[str, str]


class Communication(BaseModel):
    phone: bool
    message: bool

class AdCreate(BaseModel):
    title: str | None = None
    description: str
    price: str
    location: Location
    communication: Communication
    fields: Dict[str, str]



class PostImage(BaseModel):
    id: int
    uuid: UUID


class PostImageResolutions(str, Enum):
    small_square = "100x100"
    medium_square = "200x200"
    large_square = "300x300"
    medium = "640x480"
    large = "1280x960"


# Модель Ad для валидации входных данных
class AdModel(BaseModel):
    id: str


# Модель Location для вывода
class LocationDetail(BaseModel):
    country: Optional[str]
    lat: Optional[str] = None
    long: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None


class LocationOutModel(BaseModel):
    address: str
    full_address: str
    detail: Optional[LocationDetail] = None


# Модель AdFields для вывода
class AdFieldsOutModel(BaseModel):
    key: str
    value: str


# Модель Owner для вывода
class OwnerOutModel(BaseModel):
    id: int
    name: Optional[str] = None
    photo: UUID | None = None
    rating: Optional[float] = None
    feedback_count: Optional[int] = None
    phone: Optional[str] = None
    online: bool
    online_at: datetime.datetime | None = None
    is_active: bool
    adv_count: Optional[int] = None
    adv: Optional[list] = None

    class Config:
        orm_mode = True


# Модель Ad для вывода
class AdOutModel(BaseModel):
    id: UUID
    title: str
    description: str
    price: int
    location: Dict[str, Any] = {}
    communication: dict
    fields: dict
    photos: list
    favorite: bool
    created_at: str
    views: int
    status: str
    owner: OwnerOutModel

    class Config:
        orm_mode = True


class AdCatalogOutModel(BaseModel):
    id: UUID
    title: str
    description: str
    price: int
    location: Dict[str, Any] = {}
    communication: dict
    fields: dict
    photos: list


class ItemsOutModel(BaseModel):
    id: UUID
    title: str
    description: str
    price: str
    location: Dict[str, Any] = {}
    photos: Union[UUID, str]
    favorite: bool
    status: str
    created_at: str


class PaginatedItems(BaseModel):
    total: int
    items: List[ItemsOutModel]


class ChangeAdStatusModel(BaseModel):
    status: str


class AddOrEditAdvModel(BaseModel):
    id: UUID


class AdvAndCatalogModel(BaseModel):
    ad_info: AdCatalogOutModel
    catalog_info: CatalogSchemaAdditionalFields

