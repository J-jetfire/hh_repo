from fastapi import APIRouter, Depends, HTTPException, Body, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from pydantic.error_wrappers import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_current_time, get_current_time2
from app.crud import (
    user as user_crud,
    devices as devices_crud,
    phone as phone_crud
)
from app.db.db_models import User
from app.logger import setup_logger, setup_logger_refresh
from app.schemas import auth as auth_schemas, user as user_schemas
from app.utils import dependencies, security, exception, \
    devices as devices_utils
from app.crud.user import get_current_user as get_user, change_notification_auth, get_user_by_id

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = setup_logger(__name__)
logger_refresh = setup_logger_refresh(__name__)


@router.post(
    "/registration",
    summary="Registration User",
    status_code=status.HTTP_201_CREATED,
    response_model=auth_schemas.ResponseSuccess,
    responses={
        400: exception.custom_errors("Bad Request", [{
            "msg": "Подтвердите согласие. Статус ошибки 400"
        }]),
        403: exception.custom_errors("Validation Error", [{
            "msg": "Ошибка валидации пароля"
        }]),
        404: exception.custom_errors("Bad Request", [{
            "msg": "Непредвиденная ошибка, попробуйте позже"
        }]),
        409: exception.custom_errors("Conflict", [{
            "msg": "Пользователь уже существует"
        }])
    }
)
async def registration(
        user_data: user_schemas.UserRegistration,
        user_phone: str = Depends(security.decode_phone_token),
        db: Session = Depends(dependencies.get_db)
):
    phone = user_phone
    if not user_data.agree:
        raise HTTPException(status_code=400, detail={
            "msg": "Подтвердите согласие"
        })
    try:
        user = user_schemas.UserCreate(**user_data.dict(), phone=phone)
    except ValidationError:
        raise HTTPException(status_code=403, detail={
            "msg": "Ошибка валидации пароля"
        })
    new_user = user_crud.create_user(user=user, db=db)
    if not new_user:
        raise exception.user_exists
    return {"msg": "success"}


@router.post(
    "/registration-google",
    summary="Sign in with Google",
    status_code=200,
    response_model=auth_schemas.ResponseTokensGoogle
)
async def registration_google(
        google_data: auth_schemas.RequestDeviceData,
        db: Session = Depends(dependencies.get_db)
):
    token_data = security.decode_google_token(google_data.token,
                                              google_data.system)
    if not token_data:
        raise HTTPException(status_code=400, detail={
            "msg": "Невалидный токен"
        })

    google_id = token_data.sub
    user = user_crud.get_user_by_google_id(db, google_id)
    if user:
        db_device = user_schemas.UserDevicesCreate(
            **devices_utils.json_parse(google_data.device)
        )
        token_data = {
            "sub": str(user.id),
            "device": str(db_device.uniqueId)
        }
        access_token = security.create_access_token(data=token_data)
        refresh_token = security.create_refresh_token(data=token_data)

        devices_crud.create_user_device(
            user=user,
            device=db_device,
            token=refresh_token, db=db)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "verify_phone": user.phoneVerified,
            "user_id": user.id}

    if not user:
        user_data = user_schemas.UserCreateOauth(
            googleId=google_id,
            email=token_data.email,
            name=token_data.given_name,
            photo=token_data.picture,
            password=security.hash_password(google_id)
        )
        user = user_crud.create_user_oauth(user=user_data, db=db)

    return {
        "access_token": "",
        "refresh_token": "",
        "verify_phone": user.phoneVerified,
        "user_id": user.id,
    }


@router.post(
    "/registration-apple",
    summary="Sign in with Apple",
    status_code=200,
    response_model=auth_schemas.ResponseTokensGoogle
)
async def registration_apple(
        apple_data: auth_schemas.RequestDeviceData,
        db: Session = Depends(dependencies.get_db)
):
    token_data = security.decode_apple_token(apple_data.token)
    if not token_data:
        raise HTTPException(status_code=400, detail={
            "msg": "Инвалид токен"
        })
    apple_id = token_data.sub
    user = user_crud.get_user_by_apple_id(db, apple_id=apple_id)
    if user:
        db_device = user_schemas.UserDevicesCreate(
            **devices_utils.json_parse(apple_data.device))
        token_data = {
            "sub": str(user.id),
            "device": str(db_device.uniqueId)
        }
        access_token = security.create_access_token(data=token_data)
        refresh_token = security.create_refresh_token(data=token_data)
        devices_crud.create_user_device(user=user,
                                        device=db_device,
                                        token=refresh_token,
                                        db=db)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "verify_phone": user.phoneVerified,
            "user_id": user.id
        }

    if not user:
        try:
            name = token_data.firstName
        except:
            name = token_data.email
        user_data = user_schemas.UserCreateOauth(appleId=apple_id,
                                                 email=token_data.email,
                                                 name=name,
                                                 password=security.hash_password(apple_id))
        user = user_crud.create_user_oauth(user=user_data, db=db)
    return {
        "access_token": "",
        "refresh_token": "",
        "verify_phone": user.phoneVerified,
        "user_id": user.id
    }


@router.post(
    "/login",
    summary="OAuth2 Login",
    status_code=200,
    response_model=auth_schemas.ResponseTokens,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Некорректные данные для входа"
        }])
    }
)
async def login(
        background_tasks: BackgroundTasks,
        form_data: OAuth2PasswordRequestForm = Depends(),
        device: str = Body(),
        db: Session = Depends(dependencies.get_db),
):
    user = user_crud.auth_user(
        username=form_data.username,
        password=form_data.password,
        db=db
    )
    if not user:
        raise HTTPException(status_code=404, detail={
            "msg": "Некорректные данные для входа"
        })
    if not devices_utils.json_parse(device):
        raise HTTPException(status_code=404, detail={
            "msg": "Некорректные данные для входа"
        })

    db_device = user_schemas.UserDevicesCreate(
        **devices_utils.json_parse(device))
    token_data = {
        "sub": str(user.id),
        "device": str(db_device.uniqueId)
    }
    access_token = security.create_access_token(token_data)
    refresh_token = security.create_refresh_token(token_data)
    devices_crud.create_user_device(user=user,
                                    device=db_device,
                                    token=refresh_token,
                                    db=db)

    is_auth = True
    background_tasks.add_task(change_notification_auth, db_device.uniqueId, is_auth)

    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post(
    "/reset-password",
    summary="Reset User password",
    status_code=200,
    response_model=auth_schemas.ResponseSuccess,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Пользователя не существует"
        }])
    }
)
async def reset_password(
        new_password: str = Body(embed=True),
        user_phone: str = Depends(security.decode_phone_token),
        db: Session = Depends(dependencies.get_db)
):
    user = user_crud.get_user_by_phone(db, user_phone)
    if not user:
        raise exception.user_not_exist
    user_crud.change_password(user=user, new_password=new_password, db=db)
    devices_crud.delete_user_devices(user, db)
    return {"msg": "success"}


@router.post(
    "/verify-phone",
    summary="Confirm User phone",
    response_model=auth_schemas.ResponseTokens,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Пользователя не существует"
        }]),
        409: exception.custom_errors("Bad Request", [{
            "msg": "Номер привязан к другому пользователю"
        }])
    }
)
async def verify_phone(
        device_data: auth_schemas.RequestDeviceData,
        user_id: int = Body(embed=True),
        social: str = Body(embed=True),
        user_phone: str = Depends(security.decode_phone_token),
        db: Session = Depends(dependencies.get_db)
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise exception.user_not_exist
    phone = user_crud.get_user_by_phone(db, user_phone)
    if phone:
        raise exception.user_exists
    phone_crud.verify_phone(db, user_phone, user)

    if social == "google":
        token_data = security.decode_google_token(device_data.token,
                                                  device_data.system)
    elif social == "apple":
        token_data = security.decode_apple_token(device_data.token)
    else:
        token_data = True

    if not token_data:
        logger.error(f"api/endpoints/auth. verify_phone. Невалидный токен")
        raise HTTPException(status_code=400, detail={
            "msg": "Невалидный токен"
        })

    db_device = user_schemas.UserDevicesCreate(
        **devices_utils.json_parse(device_data.device)
    )

    token_data = {
        "sub": str(user.id),
        "device": str(db_device.uniqueId)
    }
    access_token = security.create_access_token(data=token_data)
    refresh_token = security.create_refresh_token(data=token_data)
    devices_crud.create_user_device(user=user,
                                    device=db_device,
                                    token=refresh_token,
                                    db=db)
    return {"access_token": access_token, "refresh_token": refresh_token}


@router.get(
    "/refresh",
    summary="Refresh token",
    response_model=auth_schemas.ResponseTokens,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Устройство не найдено"
        }])
    }
)
async def refresh(
        refresh_token: str = Depends(dependencies.oauth2_scheme),
        db: Session = Depends(dependencies.get_db)
):
    check_token = devices_utils.refresh_token_verification(refresh_token, db)
    if not check_token:
        logger.error(f"/auth/refresh. 404. no check_token. Устройство не найдено")
        raise HTTPException(status_code=404, detail={
            "msg": "Устройство не найдено"
        })
    refresh_token_data = security.decode_refresh_token(refresh_token)
    user_id, device = refresh_token_data.get("sub"), refresh_token_data.get("device")
    access_token = security.create_access_token({
        "sub": user_id, "device": device})
    refresh_token_new = security.create_refresh_token({
        "sub": user_id, "device": device})
    devices_crud.update_refresh_token(refresh_token, refresh_token_new, db)
    logger_refresh.info(f"/auth/refresh. Новый созданный токен: {refresh_token_new}")
    current_user = get_user_by_id(db, user_id)
    if not current_user.online:
        current_user.online = True

    # Обновляем online_at
    current_user.online_at = get_current_time2()
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token_new}


@router.post(
    "/change_phone",
    summary="Change Authorized Users phone",
    status_code=status.HTTP_201_CREATED,
    response_model=auth_schemas.ResponseSuccess,
)
async def changing_phone(
        request: Request,
        current_user: User = Depends(get_user),
        db: Session = Depends(dependencies.get_db)
):
    if not current_user:
        raise HTTPException(
            status_code=400, detail={
                "msg": "Доступно только авторизованным пользователям"
            }
        )

    try:
        json_body = await request.json()
    except:
        json_body = {}
    user_phone = json_body.get('phone_token', None)

    if not user_phone:
        raise HTTPException(
            status_code=400, detail={
                "msg": "Введите новый номер телефона"
            }
        )

    new_phone = security.decode_phone_token(user_phone)
    old_phone = current_user.phone

    user = user_schemas.UserChangePhone(new_phone=new_phone, old_phone=old_phone)
    phone = user_crud.update_phone(user=user, db=db)

    if not phone:
        raise HTTPException(
            status_code=400, detail={
                "msg": "Ошибка изменения номера телефона"
            }
        )
    return {"msg": "success"}
