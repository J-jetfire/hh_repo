import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi.security import OAuth2PasswordRequestForm
from pydantic import UUID4
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src import utils
from src.auth.config import auth_config
from src.auth.exceptions import InvalidCredentials
from src.auth.schemas import AuthUser
from src.auth.security import check_password
from src.models import RefreshTokens, User, execute, fetch_one


async def create_user(user: AuthUser) -> dict[str, Any] | None:
    insert_query = (
        insert(User)
        .values(
            {
                "username": user.username,
                "password": user.password,
                "created_at": datetime.utcnow(),
            }
        )
        .returning(User)
    )

    return await fetch_one(insert_query)


async def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    select_query = select(User).where(User.id == user_id)
    return await fetch_one(select_query)


async def get_user_by_username(username: str, session: AsyncSession) -> dict[str, Any] | None:
    select_query = select(User).where(User.username == username)
    query = await session.execute(select_query)
    user = query.scalar_one_or_none()
    return user


async def create_refresh_token(
    *, user_id: int, refresh_token: str | None = None
) -> str:
    if not refresh_token:
        refresh_token = utils.generate_random_alphanum(64)

    insert_query = insert(RefreshTokens).values(
        uuid=uuid.uuid4(),
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(seconds=auth_config.REFRESH_TOKEN_EXP),
        user_id=user_id,
    )
    await execute(insert_query)

    return refresh_token


async def get_refresh_token(refresh_token: str) -> dict[str, Any] | None:
    select_query = select(RefreshTokens).where(
        RefreshTokens.refresh_token == refresh_token
    )

    return await fetch_one(select_query)


async def expire_refresh_token(refresh_token_uuid: UUID4) -> None:
    update_query = (
        update(RefreshTokens)
        .values(expires_at=datetime.utcnow() - timedelta(days=1))
        .where(RefreshTokens.uuid == refresh_token_uuid)
    )

    await execute(update_query)


async def authenticate_user(auth_data: OAuth2PasswordRequestForm, session: AsyncSession) -> dict[str, Any]:
    user = await get_user_by_username(auth_data.username, session)
    if not user:
        raise InvalidCredentials()

    if not check_password(auth_data.password, user.password):
        raise InvalidCredentials()

    return user
