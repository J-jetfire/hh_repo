from datetime import datetime
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import service
from src.auth.exceptions import RefreshTokenNotValid, UsernameTaken
from src.auth.schemas import AuthUser
from src.database import get_async_session, engine
from src.users.service import get_user_profile_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v2/auth/tokens", auto_error=False)


async def valid_user_create(user: AuthUser) -> AuthUser:
    async with AsyncSession(engine) as session:
        if await service.get_user_by_username(user.username, session):
            raise UsernameTaken()

        return user


async def valid_refresh_token(
    # refresh_token: str = Cookie(..., alias="refreshToken"),
    refresh_token: str = Depends(oauth2_scheme)
) -> dict[str, Any]:
    db_refresh_token = await service.get_refresh_token(refresh_token)
    if not db_refresh_token:
        raise RefreshTokenNotValid()

    if not _is_valid_refresh_token(db_refresh_token):
        raise RefreshTokenNotValid()

    return db_refresh_token


async def valid_refresh_token_user(
    refresh_token: dict[str, Any] = Depends(valid_refresh_token),
    session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    user = await get_user_profile_by_id(refresh_token["user_id"], session)
    if not user:
        raise RefreshTokenNotValid()

    return user


def _is_valid_refresh_token(db_refresh_token: dict[str, Any]) -> bool:
    return datetime.utcnow() <= db_refresh_token["expires_at"]
