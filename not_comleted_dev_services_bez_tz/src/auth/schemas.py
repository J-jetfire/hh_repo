import re

from pydantic import Field, field_validator

from src.models import CustomModel, Roles

# STRONG_PASSWORD_PATTERN = re.compile(r"^(?=.*[\d])(?=.*[!@#$%^&*])[\w!@#$%^&*]{6,128}$")
WEAK_PASSWORD_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,128}$")


class AuthUser(CustomModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=3, max_length=128)

    @field_validator("password", mode="after")
    @classmethod
    def valid_password(cls, password: str) -> str:
        if not re.match(WEAK_PASSWORD_PATTERN, password):
            raise ValueError(
                "Пароль не должен содержать "
                "спец. символы"
                # "one lower character, "
                # "one upper character, "
                # "digit or "
                # "special symbol"
            )

        return password


class JWTData(CustomModel):
    user_id: int = Field(alias="sub")
    is_active: bool = False
    is_admin: bool = False
    is_executor: bool = False
    is_customer: bool = False
    role: Roles | None


class AccessTokenResponse(CustomModel):
    access_token: str
    refresh_token: str


class RegisterUserResponse(CustomModel):
    username: str


