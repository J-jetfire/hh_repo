import datetime

from pydantic import BaseModel


class UserRegistration(BaseModel):
    username: str
    password: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    # password: str = Field(pattern=r"^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9]).{8,}$")
    password: str

    class Config:
        from_attributes = True


class AdminUserOut(BaseModel):
    id: int

    username: str | None = None
    name: str | None = None

    is_active: bool

    is_moderator: bool
    is_staff: bool
    is_admin: bool

    createdAt: datetime.datetime
    updatedAt: datetime.datetime | None = None
    lastLoginAt: datetime.datetime | None = None

    class Config:
        from_attributes = True


class ChangePasswordInput(BaseModel):
    old_password: str
    new_password: str
    repeat_password: str


class CheckUsernameInput(BaseModel):
    username: str


class RestorePasswordInput(BaseModel):
    username: str
    key: str
    new_password: str
    repeat_password: str
