from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID

from fastapi import Form
from pydantic import BaseModel


class CatalogCreate(BaseModel):
    title: str
    slug: str


class CatalogInput(BaseModel):
    title: str


class CatalogCreatedOut(BaseModel):
    id: UUID
    title: str
    slug: str
    order: Optional[int]


class ItemIngredientsInput(BaseModel):
    name: str


class ItemIngredientsOut(BaseModel):
    id: int
    name: str
    order: Optional[int]


class ItemCreate(BaseModel):
    catalog_id: UUID
    title: str
    slug: str
    price: int
    description: Optional[str] = None
    in_stock: bool = True
    out: int
    measure: str
    ingredients: List[str] = None  # Список ингредиентов


class ItemResponse(BaseModel):
    id: UUID
    catalog_id: UUID
    title: str
    slug: str
    price: int
    description: Optional[str] = None
    in_stock: bool
    is_active: bool
    out: int
    measure: str
    type: Optional[str] = None
    tax: Optional[str] = None
    order: Optional[int]
    images: List[UUID] = None
    ingredients: List[str] = None


class ItemResponseReturn(BaseModel):
    id: UUID
    title: str
    slug: str
    price: int
    description: Optional[str] = None
    in_stock: bool
    out: int
    measure: str
    amount: int
    sum: int


class CatalogOut(BaseModel):
    id: UUID
    title: str
    slug: str
    order: Optional[int]
    items: List[ItemResponse]


class CategoryOut(BaseModel):
    id: UUID
    title: str


class ReceiptResponse(BaseModel):
    id: UUID
    item_id: UUID
    order_id: UUID
    amount: int


class OrderResponse(BaseModel):
    id: UUID
    order_id: UUID
    num: str
    client: str
    delivery: str
    cutlery: int
    comment: Optional[str]  # Используем Optional, чтобы комментарий мог быть None
    status: str
    created_at: datetime
    items: List[ItemResponseReturn]
    total: int


class OrderItem(BaseModel):
    id: UUID
    amount: int


class CreateOrderInput(BaseModel):
    order_items: list[OrderItem]
    client: str
    delivery: str
    comment: str = None
    cutlery: int = None
    order_id: UUID


class ItemIngredientsEdit(BaseModel):
    name: str
