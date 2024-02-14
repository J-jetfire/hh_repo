from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    owner_id: int
    adv_id: UUID
    rating: int
    text: str
    state: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: int
    owner_id: int
    adv_id: UUID
    rating: int
    text: str
    state: str | None = None
    created_at: str


class FeedbackOwnerOut(BaseModel):
    id: int
    name: str | None = None
    photo: UUID | None = None
    rating: float
    feedback_count: int
    is_active: bool
    is_blocked: bool


class FeedbackUserOut(BaseModel):
    id: int
    name: str
    photo: str


class FeedbackAdvOut(BaseModel):
    id: UUID
    title: str


class FeedbackOut(BaseModel):
    id: UUID
    user: FeedbackUserOut
    adv: FeedbackAdvOut
    rating: int
    text: str
    state: str | None = None
    created_at: str


class FeedbackOutObject(BaseModel):
    owner: FeedbackOwnerOut
    feedback: List[FeedbackOut]