from typing import Any

from dotenv import load_dotenv
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

from src.constants import Environment

load_dotenv()


class Config(BaseSettings):
    DATABASE_URL: PostgresDsn

    SITE_DOMAIN: str = "myapp.com"

    ENVIRONMENT: Environment = Environment.PRODUCTION

    SENTRY_DSN: str | None = None

    CORS_ORIGINS: list[str]
    CORS_ORIGINS_REGEX: str | None = None
    CORS_HEADERS: list[str]

    APP_VERSION: str = "2"
    VERSION: str | None


settings = Config()

app_configs: dict[str, Any] = {"title": "App API", "version": settings.VERSION}

# if not settings.ENVIRONMENT.is_debug:
#     app_configs["openapi_url"] = None  # hide docs
