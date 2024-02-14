import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import delete

from app.database.database import get_async_session
from app.logger import setup_logger
from app.models.admin_models import AdminUser, TokenRefresh, TokenBlacklist
from app.models.models import AccessKey
from app.schemas.auth import UserRegistration, UserCreate, AdminUserOut, ChangePasswordInput, CheckUsernameInput, \
    RestorePasswordInput
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from calendar import timegm
from sqlalchemy.future import select
from jose import jwt
from jose import JWTError


router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v2/auth/login", auto_error=False)

logger = setup_logger(__name__)


@router.post(
    "/register",
    summary="Registration of Admin User",
    status_code=status.HTTP_201_CREATED
)
async def registration_admin(
        user_data: UserRegistration,
        db: AsyncSession = Depends(get_async_session)
):
    try:
        user = UserRegistration(**user_data.dict())
    except ValidationError:
        raise HTTPException(status_code=403, detail={
            "msg": "Ошибка валидации пароля"
        })
    new_user = await create_user(user=user, db=db)
    if not new_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"msg": "Имя пользователя уже существует"})
    return {"msg": "success"}


# Эндпоинт для авторизации и получения токенов, установка access_token и refresh_token в Cookie
@router.post(
    "/login",
    summary="OAuth2 Admin Login",
    status_code=200)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_async_session)
):
    user = await auth_admin_user(
        username=form_data.username,
        password=form_data.password,
        db=db
    )
    if not user:
        raise HTTPException(status_code=400, detail="Некорректные данные для входа")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"msg": "User is not active"}
        )
    if not user.is_staff:
        if not user.is_moderator:
            if not user.is_admin:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"msg": "Permission denied"}
                    )

    token_data = {
        "sub": str(user.id),
        "username": str(user.username)
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # creating refresh token and user link
    db_refresh = TokenRefresh(
        user_id=user.id,
        jti=refresh_token
    )
    db.add(db_refresh)
    await db.commit()

    response = JSONResponse(content={"access_token": access_token, "refresh_token": refresh_token})

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Max age in seconds
        secure=False,  # Set this to True for HTTPS
        httponly=True,
        samesite="strict"
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,  # Max age in seconds
        secure=False,  # Set this to True for HTTPS
        httponly=True,
        samesite="strict"
    )
    logger.info(f"Пользователь `{user.username}` авторизован")
    return response


# Эндпоинт для обновления access токена и установки refresh токена в Cookie
@router.get("/refresh")
async def refresh_token_endpoint(refresh_token: str = Depends(oauth2_scheme),
                                 db: AsyncSession = Depends(get_async_session)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing")

    if not await refresh_token_verification(refresh_token, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    if await is_token_blacklisted(refresh_token, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is revoked")

    refresh_token_data = decode_refresh_token(refresh_token)

    user_id, username = refresh_token_data.get("sub"), refresh_token_data.get("username")
    token_data = {
        "sub": str(user_id),
        "username": str(username)
    }

    access_token_new = create_access_token(token_data)
    # refresh_token_new = create_refresh_token(token_data)

    # if refresh_token == refresh_token_new:
    #     print('refresh_token:', refresh_token_new)

    # update_token = await update_refresh_token(refresh_token, refresh_token_new, db)
    # if not update_token:
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing")

    # response = JSONResponse(content={"access_token": access_token_new, "refresh_token": refresh_token_new})
    response = JSONResponse(content={"access_token": access_token_new, "refresh_token": refresh_token})

    response.set_cookie(
        key="access_token",
        value=access_token_new,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Max age in seconds
        secure=False,  # Set this to True for HTTPS
        httponly=True,
        samesite="strict"
    )

    response.set_cookie(
        key="refresh_token",
        # value=refresh_token_new,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,  # Max age in seconds
        secure=False,  # Set this to True for HTTPS
        httponly=True,
        samesite="strict"
    )

    return response


@router.post("/logout")
async def logout(refresh_token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing")

    try:
        await add_token_to_blacklist(refresh_token, db)
        return {"detail": "Successfully logged out"}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


async def create_user(db: AsyncSession, user: UserCreate):
    if await get_user_by_username(db=db, username=user.username):
        return False
    db_user = AdminUser(
        username=user.username,
        is_active=False,
        password=hash_password(user.password),
        createdAt=datetime.datetime.utcnow())
    db.add(db_user)
    await db.commit()
    logger.info(f"Зарегистрирован пользователь: `{user.username}`")
    return True


async def get_user_by_username(db: AsyncSession, username: str):
    db_user = await db.execute(select(AdminUser).where(AdminUser.username == username))
    db_user = db_user.scalar_one_or_none()
    if db_user:
        return db_user
    else:
        return False


def hash_password(password: str):
    return pwd_context.hash(password)


async def add_token_to_blacklist(jti: str, db):
    # await db.execute(TokenRefresh.delete().where(TokenRefresh.c.jti == jti))
    await db.execute(delete(TokenRefresh).where(TokenRefresh.jti == jti))
    # Добавить токен в TokenBlacklist
    token_blacklist = TokenBlacklist(jti=jti)
    db.add(token_blacklist)

    # Сохранить изменения в базе данных
    await db.commit()


def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             settings.ACCESS_TOKEN_SECRET_KEY,
                             algorithm=settings.ACCESS_TOKEN_ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             settings.REFRESH_TOKEN_SECRET_KEY,
                             algorithm=settings.REFRESH_TOKEN_ALGORITHM)
    return encoded_jwt


def decode_access_token(access_token: str = Depends(oauth2_scheme)):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(access_token, settings.ACCESS_TOKEN_SECRET_KEY,
                             algorithms=[settings.ACCESS_TOKEN_ALGORITHM])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Could not validate credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def decode_refresh_token(refresh_token: str = Depends(oauth2_scheme)):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(refresh_token, settings.REFRESH_TOKEN_SECRET_KEY,
                             algorithms=[settings.REFRESH_TOKEN_ALGORITHM])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Could not validate credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def update_refresh_token(refresh_token_old: str, refresh_token_new: str, db):
    db_refresh = await db.execute(select(TokenRefresh).where(TokenRefresh.jti == refresh_token_old))
    db_refresh = db_refresh.scalar_one_or_none()

    if not db_refresh:
        return False

    db_refresh.jti = refresh_token_new
    await db.commit()
    return True


async def is_token_blacklisted(jti: str, db):
    blacklisted = await db.execute(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
    blacklisted = blacklisted.scalar_one_or_none()
    # return db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None
    return blacklisted


async def refresh_token_verification(refresh_token: str, db):
    refresh_data = jwt.get_unverified_claims(refresh_token)
    now = timegm(datetime.datetime.utcnow().utctimetuple())
    exp, user_id = refresh_data['exp'], refresh_data['sub']
    # TokenRefresh
    # Проверка токена на существование
    db_refresh_tokens = await db.execute(select(TokenRefresh).where(TokenRefresh.user_id == int(user_id)))
    db_refresh_tokens = db_refresh_tokens.scalars().all()

    for db_refresh_token in db_refresh_tokens:
        if db_refresh_token.jti == refresh_token and now > exp:
            await db.execute(TokenRefresh.delete().where(TokenRefresh.c.jti == refresh_token))
            await db.commit()
            return False
        else:
            return True
    return False


async def auth_admin_user(username: str, password: str, db):
    db_user = await get_user_by_username(db=db, username=username)
    if not db_user:
        return False
    if not await verify_password(password, db_user.password):
        return False
    db_user.lastLoginAt = datetime.datetime.utcnow()
    await db.commit()
    return db_user


async def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


async def get_user_by_id(db: AsyncSession, user_id: int):
    db_user = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    db_user = db_user.scalar_one_or_none()
    if db_user:
        return db_user
    else:
        return False


async def get_current_user(db: AsyncSession = Depends(get_async_session), access_token: str = Depends(oauth2_scheme)):
    try:
        token_data = decode_access_token(access_token)
        user_id = int(token_data.get("sub"))

        user = await get_user_by_id(db=db, user_id=user_id)

        if not user:
            # raise HTTPException(
            #     status_code=status.HTTP_401_UNAUTHORIZED,
            #     detail={"msg": "Could not validate credentials"},
            #     headers={"WWW-Authenticate": "Bearer"},
            # )
            return None

        return user
    except Exception as e:
        return None


async def get_current_active_user_or_none(current_user: AdminUser = Depends(get_current_user)):
    if current_user:
        if not current_user.is_active:
            return None

        if not current_user.is_moderator:
            if not current_user.is_admin:
                return None
        return current_user
    else:
        return None


async def get_current_active_user(current_user: AdminUser = Depends(get_current_user)):
    if current_user:
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        if not current_user.is_moderator:
            if not current_user.is_admin:
                raise HTTPException(status_code=403, detail="Permission denied")
        return current_user
    else:
        raise HTTPException(status_code=403, detail="Permission denied")


async def get_current_staff_user(current_user: AdminUser = Depends(get_current_user)):
    if current_user:
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        # check if staff or moderator
        if not current_user.is_staff:
            if not current_user.is_moderator:
                if not current_user.is_admin:
                    raise HTTPException(status_code=403, detail="Permission denied")

        return current_user
    else:
        raise HTTPException(status_code=403, detail="Permission denied")


@router.get("/user/me", summary="Get current User",
            response_model=AdminUserOut)
async def get_me(current_user: AdminUser = Depends(get_current_staff_user)):
    """
    Получение авторизованного пользователя.

    Параметры:
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - Объект пользователя
    """
    return current_user


@router.post(
    "/change-password",
    summary="Change Password",
    status_code=status.HTTP_202_ACCEPTED
)
async def change_password(
        password_data: ChangePasswordInput = Body(...),
        current_user: AdminUser = Depends(get_current_staff_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Смена пароля для авторизованного пользователя.

    Параметры:
    - password_data (ChangePasswordInput): Данные с формой JSON.
    - current_user (AdminUser): Объект авторизованного пользователя.
    - db (AsyncSession): Сессия базы данных.

    Возвращает:
    - Сообщение об успешной смене пароля.
    """
    # Проверка соответствия старого пароля

    # if not await verify_password(password, db_user.password):
    #     return False

    if password_data.new_password != password_data.repeat_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Введенный пароль и повтор пароля должны быть одинаковые"
        )

    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Введенный старый пароль и новый должны отличаться"
        )

    if not await verify_password(password_data.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный текущий пароль"
        )

    # Проверка совпадения нового пароля и повтора пароля
    if password_data.new_password != password_data.repeat_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль и повтор пароля не совпадают"
        )

    # Изменение пароля пользователя
    current_user.password = hash_password(password_data.new_password)
    await db.commit()

    return "success"


@router.post(
    "/check-username",
    summary="Check Username",
    status_code=status.HTTP_200_OK
)
async def check_username(
        data: CheckUsernameInput = Body(...),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Поиск пользователя по username.

    Параметры:
    - username (CheckUsernameInput): Имя пользователя.
    - db (AsyncSession): Сессия базы данных.

    Возвращает:
    - Сообщение о существовании пользователя.
    """
    user = await db.execute(select(AdminUser).where(AdminUser.username == data.username))
    user = user.scalar_one_or_none()

    if user:
        return True
    return False


@router.post(
    "/restore-password",
    summary="Restore Password",
    status_code=status.HTTP_202_ACCEPTED
)
async def restore_password(
        data: RestorePasswordInput = Body(...),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Поиск пользователя по username.

    Параметры:
    - username (CheckUsernameInput): Имя пользователя.
    - db (AsyncSession): Сессия базы данных.

    Возвращает:
    - Сообщение о существовании пользователя.
    """
    if data.new_password != data.repeat_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль и повтор пароля не совпадают"
        )

    user = await db.execute(select(AdminUser).where(AdminUser.username == data.username))
    user = user.scalar_one_or_none()

    if user:
        db_key = await db.execute(select(AccessKey).where(AccessKey.id == 1))
        db_key = db_key.scalar_one_or_none()
        db_key = db_key.key
        if db_key:
            if await verify_password(data.key, db_key):
                user.password = hash_password(data.new_password)
                await db.commit()
                return True
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Секретное слово недействительно"
                )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Пользователь не найден"
    )


@router.get(
    "/secretkey/",
    summary="PreviewSecretKey",
    status_code=status.HTTP_202_ACCEPTED
)
async def preview_secretkey():
    return "Введите в конце адресной строки Секретное слово без пробелов и спец.символов"


@router.get(
    "/secretkey/{key}",
    summary="Set/Update SecretKey",
    status_code=status.HTTP_202_ACCEPTED
)
async def set_secretkey(
        key: str,
        db: AsyncSession = Depends(get_async_session)
):
    """
    Создание или изменение секретного слова

    Параметры:
    - key: Секретное слово.
    - db (AsyncSession): Сессия базы данных.

    Возвращает:
    - Сообщение о создании или изменении секретного слова
    """

    db_key = await db.execute(select(AccessKey).where(AccessKey.id == 1))
    db_key = db_key.scalar_one_or_none()
    if db_key:
        print('key', key)
        hashed_key = hash_password(key)
        if await verify_password(key, db_key.key):
            print('same keys')
            return "Введенный вами ключ уже был установлен в системе"

        db_key.key = hashed_key
    else:
        new_key = AccessKey(id=1, key=hash_password(key))
        db.add(new_key)
        print('new_key', key)

    # Commit the changes to the database
    await db.commit()

    return "Секретное слово было успешно создано/обновлено!"
