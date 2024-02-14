import hashlib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from fastapi.staticfiles import StaticFiles
from app.api.routers import api_router
from app.core.config import settings
from app.db.db_models import Base
from app.db.session import engine
import asyncio
from app.logger import setup_logger
from pathlib import Path
import sentry_sdk

Base.metadata.create_all(bind=engine)

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

app = FastAPI(
    title=settings.TITLE,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    root_path=settings.OPENAPI_PREFIX,
    debug=True
)

static_path = str(Path(__file__).parent.parent / "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

ip_requests = {}
lock = asyncio.Lock()
logger = setup_logger(__name__)


# Фильтрация запросов по IP-адресу
@app.middleware("http")
async def restrict_ips(request: Request, call_next):
    # client_ip = request.client.host
    client_ip = request.headers.get('CF-Connecting-IP', None)

    # Принятие запросов только из списка разрешенных
    # if client_ip not in settings.ALLOWED_IPS:
    #     error_response = JSONResponse(
    #         status_code=403,
    #         content={"detail": "Доступ запрещен для данного IP-адреса"}
    #     )
    #     return error_response

    # Отклонение запросов из списка запрещенных
    if client_ip in settings.BLACKLIST_IPS:
        logger.error(f"Доступ запрещен для данного IP-адреса: {client_ip}")
        error_response = JSONResponse(
            status_code=403,
            content={"detail": "Доступ запрещен для данного IP-адреса"}
        )
        return error_response

    response = await call_next(request)
    return response


# Лимит на кол-во запросов с одного IP
# @app.middleware("http")
# async def rate_limiting(request: Request, call_next):
#     # client_ip = request.client.host
#     client_ip = request.headers.get('CF-Connecting-IP', None)
#
#     async with lock:
#         if client_ip not in ip_requests:
#             ip_requests[client_ip] = []
#
#         current_time = time.time()
#         recent_requests = [t for t in ip_requests[client_ip] if current_time - t <= settings.TIME_LIMIT]
#
#         if len(recent_requests) >= settings.REQUEST_LIMIT:
#             remaining_time = settings.TIME_LIMIT - (current_time - recent_requests[0])
#             logger.error(f"Превышен лимит запросов с IP: {client_ip}")
#             return JSONResponse(
#                 status_code=429,
#                 content={"detail": f"Превышен лимит запросов. Повторите через {remaining_time:.2f} секунд"}
#             )
#
#         ip_requests[client_ip] = recent_requests + [current_time]
#
#     logger.info(f"Выполнен запрос с IP: {client_ip}")
#
#     try:
#         response = await call_next(request)
#     except Exception as e:
#         logger.error(f"Произошла ошибка при обработке запроса: {e}")
#         return JSONResponse(
#             status_code=500,
#             content={"detail": "Произошла ошибка при обработке запроса"}
#         )
#
#     return response


# Проверка API_KEY и User-Agent в запросах
# @app.middleware("http")
# async def check_headers(request: Request, call_next):
#     # user_agent = request.headers.get("User-Agent")
#     # api_key = request.headers.get("X-API-Key")
#     api_key = request.headers.get("x-api-key")
#     # if user_agent != settings.EXPECTED_USER_AGENT or hashlib.sha256(api_key.encode()).hexdigest() != settings.APP_API_KEY:
#     if not api_key or hashlib.sha256(api_key.encode()).hexdigest() != settings.APP_API_KEY:
#         error_response = JSONResponse(
#             status_code=403,
#             content={"detail": "Недопустимый запрос"}
#         )
#         return error_response
#
#     response = await call_next(request)
#     return response


app.include_router(api_router)

# origins = [
#     "http://localhost",
#     "http://localhost:3000",
#     "http://192.168.88.11",
#     "http://192.168.88.11:3000",
#     "http://192.168.88.191"
# ]

app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Добавьте путь монтирования для определения API
app.openapi_url = "/kvik_v3/openapi.json"


@app.on_event("startup")
async def startup_event():
    redis = aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", encoding="utf8",
                              decode_responses=True)
    FastAPICache.init(RedisBackend(redis), prefix="kvik-cache")
