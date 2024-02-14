from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from src.auth.config import auth_config
from src.auth.exceptions import AuthorizationFailed, AuthRequired, InvalidToken
from src.auth.schemas import JWTData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/tokens", auto_error=False)


def create_access_token(
    *,
    user: dict[str, Any],
    expires_delta: timedelta = timedelta(minutes=auth_config.JWT_EXP),
) -> str:

    jwt_data = {
        "sub": str(user.id),
        "exp": datetime.utcnow() + expires_delta,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "is_executor": user.is_executor,
        "is_customer": user.is_customer,
        "role": user.role.value
    }

    return jwt.encode(jwt_data, auth_config.JWT_SECRET, algorithm=auth_config.JWT_ALG)


async def parse_jwt_user_data_optional(
    token: str = Depends(oauth2_scheme),
) -> JWTData | None:
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, auth_config.JWT_SECRET, algorithms=[auth_config.JWT_ALG]
        )
    except JWTError:
        raise InvalidToken()

    return JWTData(**payload)


async def parse_jwt_user_data(
    token: JWTData | None = Depends(parse_jwt_user_data_optional),
) -> JWTData:

    if not token:
        raise AuthRequired()

    if not token.is_active:
        raise AuthRequired()

    return token


# Get AdminUser data
async def parse_jwt_admin_data(
    token: JWTData = Depends(parse_jwt_user_data),
) -> JWTData:

    if not token.is_admin:
        raise AuthorizationFailed()

    return token


# Authorize AdminAccess without data
async def validate_admin_access(
    token: JWTData | None = Depends(parse_jwt_user_data_optional),
) -> None:
    if token and token.is_active and token.is_admin:
        return

    raise AuthorizationFailed()


# Authorize CustomerAccess without data
async def validate_customer_access(
    token: JWTData | None = Depends(parse_jwt_user_data_optional),
) -> None:
    if token and token.is_active and token.is_customer:
        return

    raise AuthorizationFailed()


# Authorize ExecutorAccess without data
async def validate_executor_access(
    token: JWTData | None = Depends(parse_jwt_user_data_optional),
) -> None:
    if token and token.is_active and token.is_executor:
        return

    raise AuthorizationFailed()


# Authorize UserAccess without data
async def validate_users_access(
    token: JWTData | None = Depends(parse_jwt_user_data_optional),
) -> None:
    if token and token.is_active:
        return

    raise AuthorizationFailed()
