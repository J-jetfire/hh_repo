import datetime

from fastapi import Depends
from google.auth.transport import requests
from google.oauth2 import id_token
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.logger import setup_logger
from app.schemas import auth as auth_schema
from app.utils import exception, dependencies

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = setup_logger(__name__)

def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_phone_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + \
                 datetime.timedelta(minutes=settings.PHONE_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             settings.PHONE_TOKEN_SECRET_KEY,
                             algorithm=settings.PHONE_TOKEN_ALGORITHM)
    return encoded_jwt


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
        expire = datetime.datetime.utcnow() + \
                 datetime.timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             settings.REFRESH_TOKEN_SECRET_KEY,
                             algorithm=settings.REFRESH_TOKEN_ALGORITHM)
    return encoded_jwt


def decode_phone_token(access_token: str = Depends(dependencies.oauth2_scheme)):
    if not access_token:
        raise exception.not_authenticated_exception
    try:
        payload = jwt.decode(access_token, settings.PHONE_TOKEN_SECRET_KEY,
                             algorithms=[settings.PHONE_TOKEN_ALGORITHM])
        user_phone = payload.get("sub")
    except Exception:
        logger.error(f"utils/security- decode_phone_token. Ошибка декодирования токена")
        raise exception.unexpected_error
    return user_phone


def decode_access_token(access_token: str = Depends(dependencies.oauth2_scheme)):
    if not access_token:
        raise exception.not_authenticated_exception
    try:
        payload = jwt.decode(access_token, settings.ACCESS_TOKEN_SECRET_KEY,
                             algorithms=[settings.ACCESS_TOKEN_ALGORITHM])
    except Exception:
        logger.error(f"utils/security- decode_access_token. Ошибка декодирования токена")
        raise exception.credentials_exception
    return payload


def decode_refresh_token(refresh_token: str = Depends(dependencies.oauth2_scheme)):
    if not refresh_token:
        raise exception.not_authenticated_exception
    try:
        payload = jwt.decode(refresh_token, settings.REFRESH_TOKEN_SECRET_KEY,
                             algorithms=[settings.REFRESH_TOKEN_ALGORITHM])
    except Exception:
        logger.error(f"utils/security- decode_refresh_token. Ошибка декодирования токена")
        raise exception.credentials_exception
    return payload


def decode_google_token(token: str, system: str):
    #TODO: рефакторинг
    try:
        if system == "ios":
            payload = id_token.verify_oauth2_token(token, requests.Request(),
                                                   settings.google_Client_ID_ios)
        else:
            payload = id_token.verify_oauth2_token(token, requests.Request(),
                                                   settings.google_Client_ID_android)
        token_info = auth_schema.GoogleTokenData(**payload)
        return token_info
    except Exception:
        logger.error(f"utils/security- decode_google_token. Ошибка декодирования токена")
        return False


#TODO: проверить на безопасность
def decode_apple_token(token: str):
    try:
        payload = jwt.get_unverified_claims(token)
        token_data = auth_schema.AppleTokenData(**payload)
        return token_data
    except Exception:
        logger.error(f"utils/security- decode_apple_token. Ошибка декодирования токена")
        return False


def encode_withdraw_token(service_id: str, amount: int, user_id: int):
    # service_id = "f5950b45-b4a5-40f4-8a9a-e8488134469b"  # Идентификатор услуги (:UUID)
    # amount = 500  # Сумма покупки (:int)
    # user_id = 63  # Идентификатор пользователя (:int)

    # Срок действия токена (~3 минуты) (:str)
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.WITHDRAW_TOKEN_EXPIRE_MINUTES)

    payload = {
        "service_id": service_id,
        "amount": amount,
        "user_id": user_id,
        "exp": expire
    }

    generated_token = jwt.encode(payload, settings.WITHDRAW_TOKEN_SECRET_KEY, algorithm=settings.WITHDRAW_TOKEN_ALGORITHM)

    return generated_token


def decode_withdraw_token(token: str):
    try:
        # settings.WITHDRAW_TOKEN_SECRET_KEY
        # settings.WITHDRAW_TOKEN_ALGORITHM
        # settings.WITHDRAW_TOKEN_EXPIRE_MINUTES

        payload = jwt.decode(token, settings.WITHDRAW_TOKEN_SECRET_KEY, algorithms=[settings.WITHDRAW_TOKEN_ALGORITHM])

        # Check if expired (payload["exp"])
        current_time = datetime.datetime.utcnow()
        if "exp" in payload and current_time > datetime.datetime.utcfromtimestamp(payload["exp"]):
            raise jwt.ExpiredSignatureError("Недействительный токен")

        service_id_from_token = payload["service_id"]  # Идентификатор услуги
        amount_from_token = payload["amount"]  # Сумма покупки
        user_id_from_token = payload["user_id"]  # Идентификатор пользователя

        response = {
            "service_id": service_id_from_token,
            "amount": amount_from_token,
            "user_id": user_id_from_token
        }

        return response

    except jwt.ExpiredSignatureError:
        print("Недействительный токен")
        logger.error(f"utils/security- decode_withdraw_token. Недействительный токен")
        return None

    except Exception:
        logger.error(f"utils/security- decode_withdraw_token. Ошибка декодирования токена")
        return None
