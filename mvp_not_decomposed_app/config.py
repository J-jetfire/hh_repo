import os
from os.path import join, dirname
from typing import ClassVar
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


class Settings(BaseSettings):
    TITLE: str = "Arena Delivery"
    DESCRIPTION: str = "Arena Delivery API"
    VERSION: str = "1.0"
    OPENAPI_PREFIX: str = os.getenv("OPENAPI_PREFIX")

    EXPECTED_USER_AGENT: str = os.getenv("EXPECTED_USER_AGENT")
    APP_API_KEY: str = os.getenv("APP_API_KEY")
    ALLOWED_IPS: list = os.getenv("ALLOWED_IPS")
    REQUEST_LIMIT: int = os.getenv("REQUEST_LIMIT")
    TIME_LIMIT: int = os.getenv("TIME_LIMIT")

    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    DATABASE_URL: ClassVar[str] = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@" \
                                  f"{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

    ACCESS_TOKEN_SECRET_KEY: str = os.getenv("ACCESS_TOKEN_SECRET_KEY")
    ACCESS_TOKEN_ALGORITHM: str = os.getenv("ACCESS_TOKEN_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_SECRET_KEY: str = os.getenv("REFRESH_TOKEN_SECRET_KEY")
    REFRESH_TOKEN_ALGORITHM: str = os.getenv("REFRESH_TOKEN_ALGORITHM")
    REFRESH_TOKEN_EXPIRE_MINUTES: int = os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES")

    PAYKEEPER_KEY: str = os.getenv("PAYKEEPER_KEY")


settings = Settings()

#
# POSTGRES_SERVER = os.environ.get("POSTGRES_SERVER")
# POSTGRES_PORT = os.environ.get("POSTGRES_PORT")
# POSTGRES_DB = os.environ.get("POSTGRES_DB")
# POSTGRES_USER = os.environ.get("POSTGRES_USER")
# POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
