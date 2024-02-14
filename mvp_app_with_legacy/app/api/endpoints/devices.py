from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session

from app.crud import user as user_crud, devices as devices_crud
from app.crud.user import change_notification_auth, delete_all_notification_auth
from app.logger import setup_logger
from app.schemas import user as user_schemas
from app.utils import exception, devices as devices_utils
from app.utils.dependencies import get_db

router = APIRouter(prefix="/devices", tags=["Devices"])
logger = setup_logger(__name__)

@router.get(
    "",
    summary="Get User devices",
    status_code=200,
    response_model=list[user_schemas.UserDevicesOut]
)
async def devices_list(
        user: user_schemas.UserOut = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    devices = devices_crud.get_user_devices(user, db)
    return devices


@router.delete(
    "",
    summary="Delete User device",
    status_code=204,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Устройство не найдено"
        }])
    }
)
async def device_delete(
        background_tasks: BackgroundTasks,
        uniqueId: str = Body(embed=True),
        user: user_schemas.UserOut = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    delete_device = devices_crud.delete_user_device(user, uniqueId, db)

    is_auth = False
    background_tasks.add_task(change_notification_auth, uniqueId, is_auth)

    if not delete_device:
        logger.error(f"api/endpoints/devices- device_delete. Устройство не найдено: {uniqueId}")
        raise HTTPException(status_code=404, detail={
            "msg": "Устройство не найдено в бд"
        })


@router.delete(
    "/all",
    summary="Delete all User devices except current",
    status_code=204,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Устройства не найдены"
        }])
    }
)
async def devices_delete_all(
        background_tasks: BackgroundTasks,
        refresh_token: str = Body(embed=True),
        user: user_schemas.UserOut = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    check_token = devices_utils.refresh_token_verification(refresh_token, db)
    if not check_token:
        logger.error(f"api/endpoints/devices- devices_delete_all. Ошибка аутентификации рефреш токена: {refresh_token}")
        raise HTTPException(status_code=404, detail={
            "msg": "Непредвиденная ошибка"
        })
    background_tasks.add_task(delete_all_notification_auth, user.id, refresh_token, db)
    delete_devices = devices_crud.delete_user_devices_except_current(
        refresh_token, user, db)
    if not delete_devices:
        logger.error(f"api/endpoints/devices- devices_delete_all. Устройства не найдены")
        raise HTTPException(status_code=404, detail={
            "msg": "Устройства не найдены"
        })


# @router.get("/test_notify")
# async def devices_delete_all_test(
#         db: Session = Depends(get_db)
# ):
#     user_id = 7
#     response = await delete_all_notification_auth(user_id, db)
#     return response
