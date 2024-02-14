from fastapi import APIRouter

from app.api.endpoints import (
    user,
    auth,
    phone,
    devices,
    catalog,
    car_directory,
    quarter,
    ad,
    image,
    main,
    feedbacks,
    subscription
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(user.router)
api_router.include_router(auth.router)
api_router.include_router(phone.router)
api_router.include_router(devices.router)
api_router.include_router(catalog.router)
api_router.include_router(car_directory.router)
api_router.include_router(quarter.router)
api_router.include_router(ad.router)
api_router.include_router(image.router)
api_router.include_router(main.router)
api_router.include_router(feedbacks.router)
api_router.include_router(subscription.router)
