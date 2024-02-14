from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.auth.router import router as auth_router
from src.config import app_configs, settings
from src.database import create_tables
from src.users.router import router as users_router
from src.services.router import router as services_router

app = FastAPI(**app_configs, root_path="/api/v2")
app.mount("/static", StaticFiles(directory="static"), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGINS_REGEX,
    allow_credentials=True,
    allow_methods=("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
    allow_headers=settings.CORS_HEADERS,
)


@app.get("/healthcheck", include_in_schema=False)
async def healthcheck() -> dict[str, str]:
    await create_tables()
    print(settings.ENVIRONMENT)
    print(settings.SITE_DOMAIN)
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(services_router, prefix="/services", tags=["Services"])


@app.on_event("startup")
async def startup_event():
    pass


# @router.get("/perfect-ping")
# async def perfect_ping():
#     await asyncio.sleep(10) # non-blocking I/O operation
#     pong = await service.async_get_pong()  # non-blocking I/O db call
#
#     return {"pong": pong}


# from fastapi import APIRouter, status
#
# router = APIRouter()
#
# @router.post(
#     "/endpoints",
#     response_model=DefaultResponseModel,  # default response pydantic model
#     status_code=status.HTTP_201_CREATED,  # default status code
#     description="Description of the well documented endpoint",
#     tags=["Endpoint Category"],
#     summary="Summary of the Endpoint",
#     responses={
#         status.HTTP_200_OK: {
#             "model": OkResponse, # custom pydantic model for 200 response
#             "description": "Ok Response",
#         },
#         status.HTTP_201_CREATED: {
#             "model": CreatedResponse,  # custom pydantic model for 201 response
#             "description": "Creates something from user request ",
#         },
#         status.HTTP_202_ACCEPTED: {
#             "model": AcceptedResponse,  # custom pydantic model for 202 response
#             "description": "Accepts request and handles it later",
#         },
#     },
# )
# async def documented_route():
#     pass
