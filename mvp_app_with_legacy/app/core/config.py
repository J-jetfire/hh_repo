import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pydantic import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    TITLE: str = os.getenv("TITLE")
    DESCRIPTION: str = os.getenv("DESCRIPTION")
    VERSION: str = os.getenv("VERSION")
    OPENAPI_PREFIX: str = os.getenv("OPENAPI_PREFIX")

    NOTIFICATION_TOKEN_URL: str = os.getenv("NOTIFICATION_TOKEN_URL")
    NOTIFICATION_TOKEN_PATH: str = os.getenv("NOTIFICATION_TOKEN_PATH")

    EXPECTED_USER_AGENT: str = os.getenv("EXPECTED_USER_AGENT")
    APP_API_KEY: str = os.getenv("APP_API_KEY")
    ALLOWED_IPS: list = os.getenv("ALLOWED_IPS")
    BLACKLIST_IPS: list = os.getenv("BLACKLIST_IPS")
    REQUEST_LIMIT: int = os.getenv("REQUEST_LIMIT")
    TIME_LIMIT: int = os.getenv("TIME_LIMIT")

    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@" \
                   f"{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

    TEST_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@" \
                   f"{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

    ONLINE_USER_EXPIRE_MINUTES: int = os.getenv("ONLINE_USER_EXPIRE_MINUTES")

    ACCESS_TOKEN_SECRET_KEY: str = os.getenv("ACCESS_TOKEN_SECRET_KEY")
    ACCESS_TOKEN_ALGORITHM: str = os.getenv("ACCESS_TOKEN_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_SECRET_KEY: str = os.getenv("REFRESH_TOKEN_SECRET_KEY")
    REFRESH_TOKEN_ALGORITHM: str = os.getenv("REFRESH_TOKEN_ALGORITHM")
    REFRESH_TOKEN_EXPIRE_MINUTES: int = os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES")
    PHONE_TOKEN_SECRET_KEY: str = os.getenv("PHONE_TOKEN_SECRET_KEY")
    PHONE_TOKEN_ALGORITHM: str = os.getenv("PHONE_TOKEN_ALGORITHM")
    PHONE_TOKEN_EXPIRE_MINUTES: int = os.getenv("PHONE_TOKEN_EXPIRE_MINUTES")

    WITHDRAW_TOKEN_SECRET_KEY: str = os.getenv("WITHDRAW_TOKEN_SECRET_KEY")
    WITHDRAW_TOKEN_ALGORITHM: str = os.getenv("WITHDRAW_TOKEN_ALGORITHM")
    WITHDRAW_TOKEN_EXPIRE_MINUTES: int = os.getenv("WITHDRAW_TOKEN_EXPIRE_MINUTES")

    FIRST_BLOCK_CALL_MINUTES: int = os.getenv("FIRST_BLOCK_CALL_MINUTES")
    SECOND_BLOCK_CALL_MINUTES: int = os.getenv("SECOND_BLOCK_CALL_MINUTES")
    CALL_CODE_TIME_MINUTE: int = os.getenv("CALL_CODE_TIME_MINUTE")

    google_Client_ID_ios: str = os.getenv("google_Client_ID_ios")
    google_Client_ID_android: str = os.getenv("google_Client_ID_android")
    google_Client_Secret: str = os.getenv("google_Client_Secret")

    VOICEPASSWORD_API_KEY: str = os.getenv("VOICEPASSWORD_API_KEY")
    VOICEPASSWORD_API_URL: str = os.getenv("VOICEPASSWORD_API_URL")

    TELEFON_IP_API_URL: str = os.getenv("TELEFON_IP_API_URL")

    REDIS_HOST: str = os.getenv("REDIS_HOST")
    REDIS_PORT: str = os.getenv("REDIS_PORT")

    MODE: str = os.getenv("MODE")

    SENTRY_DSN: str = os.getenv("SENTRY_DSN")


settings = Settings()


def get_current_time():
    # Получите текущую дату и время с учетом UTC
    current_datetime_utc = datetime.now(timezone.utc)
    # Установите желаемый часовой пояс (например, Europe/Moscow)
    tz_moscow = timezone(timedelta(hours=5))
    current_datetime_msk = current_datetime_utc.astimezone(tz_moscow)
    return current_datetime_msk


def get_current_time2():
    now = datetime.now()
    # print('datetime.now', now)
    # target_timezone = pytz.timezone('Etc/GMT-5')
    # adjusted_time = now.astimezone(target_timezone) + timedelta(hours=5)
    adjusted_time = now
    return adjusted_time
