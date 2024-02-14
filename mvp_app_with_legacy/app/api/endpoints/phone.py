from fastapi import APIRouter, Depends, Path, HTTPException
from pydantic import constr
from sqlalchemy.orm import Session

from app.crud import phone as phone_crud, user as user_crud
from app.db.db_models import User
from app.logger import setup_logger
from app.schemas import auth as auth_schemas
from app.utils import security, phone as phone_utils, exception
from app.utils.dependencies import get_db
from app.crud.user import get_current_user as get_user


router = APIRouter(prefix="/phone", tags=["Phone"])
logger = setup_logger(__name__)

@router.get(
    "/registration/{phone}",
    summary="Registration call",
    response_model=auth_schemas.ResponseSuccess,
    responses={
        400: exception.custom_errors("Bad Request", [{
            "msg": "Пользователь с таким номером уже существует"
        }])
    }
)
async def create_call_registration(
        phone: constr(regex=r"^(\+)[7][0-9]{10}$") = Path(),
        db: Session = Depends(get_db)
):
    phone_exist = user_crud.get_user_by_phone(db, phone)
    if phone_exist:
        logger.info(f"api/endpoints/phone- create_call_registration. Пользователь с таким номером уже существует: {phone_exist}")
        raise HTTPException(
            status_code=400, detail={
                "msg": "Пользователь с таким номером уже существует"
            }
        )
    phone_crud.check_phone_blocking(phone, db)
    call_result = phone_utils.call(phone=phone)

    if call_result["result"] == "ok":
        code = call_result["code"]
        phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
        return {"msg": "success"}
    else:
        logger.error(f"api/endpoints/phone- create_call_registration. Ошибка сервиса звонков: {call_result['error_code']}")
        phone_utils.error_handler(call_result["error_code"])


    # err = "Increased the number of shipments per phone"
    #
    # if call_result["success"]:
    #     code = call_result["data"]["code"]
    #     phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
    #     return {"msg": "success"}
    # else:
    #     if err in call_result["error"]:
    #         raise HTTPException(status_code=404, detail={"msg": f"Превышен лимит звонков на номер: {phone}. Не более 5 звонков в сутки"})
    #     else:
    #         phone_utils.error_handler(call_result["error"])


@router.get(
    "/reset-password/{phone}",
    summary="Reset password call",
    response_model=auth_schemas.ResponseSuccess,
    responses={
        400: exception.custom_errors("Bad Request", [{
            "msg": "Пользователя с таким номером не существует"
        }])
    }
)
async def create_call_reset_password(
        phone: constr(regex=r"^(\+)[7][0-9]{10}$") = Path(),
        db: Session = Depends(get_db)
):
    phone_exist = user_crud.get_user_by_phone(db, phone)
    if not phone_exist:
        logger.info(
            f"api/endpoints/phone- create_call_reset_password. Пользователь с таким номером не существует: {phone_exist}")
        raise HTTPException(status_code=400, detail={
            "msg": "Пользователя с таким номером не существует"
        })
    phone_crud.check_phone_blocking(phone, db)
    call_result = phone_utils.call(phone=phone)

    if call_result["result"] == "ok":
        code = call_result["code"]
        phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
        return {"msg": "success"}
    else:
        logger.error(
            f"api/endpoints/phone- create_call_reset_password. Ошибка сервиса звонков: {call_result['error_code']}")
        phone_utils.error_handler(call_result["error_code"])

    # if call_result["success"]:
    #     code = call_result["data"]["code"]
    #     phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
    #     return {"msg": "success"}
    # else:
    #     phone_utils.error_handler(call_result["error"])


@router.get(
    "/confirm/{phone}",
    summary="Confirm phone call",
    response_model=auth_schemas.ResponseSuccess,
    responses={
        400: exception.custom_errors("Bad Request", [{
            "msg": "Пользователь с таким номером уже существует"
        }])
    }
)
async def create_call_confirm_phone(
        phone: constr(regex=r"^(\+)[7][0-9]{10}$") = Path(),
        db: Session = Depends(get_db)):
    phone_exist = user_crud.get_user_by_phone(db, phone)
    if phone_exist:
        logger.info(
            f"api/endpoints/phone- create_call_confirm_phone. Пользователь с таким номером уже существует: {phone_exist}")
        raise HTTPException(status_code=400, detail={
            "msg": "Пользователь с таким номером уже существует"
        })
    phone_crud.check_phone_blocking(phone, db)
    call_result = phone_utils.call(phone=phone)

    if call_result["result"] == "ok":
        code = call_result["code"]
        phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
        return {"msg": "success"}
    else:
        logger.error(
            f"api/endpoints/phone- create_call_confirm_phone. Ошибка сервиса звонков: {call_result['error_code']}")
        phone_utils.error_handler(call_result["error_code"])

    # if call_result["success"]:
    #     code = call_result["data"]["code"]
    #     phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
    #     return {"msg": "success"}
    # else:
    #     phone_utils.error_handler(call_result["error"])


@router.get(
    "/check_phone_code/{phone}/{code}",
    summary="Check phone code",
    response_model=auth_schemas.ResponseCheckPhoneCode,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Неверный код"
        }])
    }
)
async def check_phone_code(
        phone: constr(regex=r"^(\+)[7][0-9]{10}$") = Path(),
        code: str = Path(),
        db: Session = Depends(get_db)):
    check_verification_code = phone_crud.check_phone_code(
        db=db,
        phone=phone,
        verification_code=code
    )
    if not check_verification_code:
        logger.info(
            f"api/endpoints/phone- check_phone_code. Неверный код верификации: {code}")
        raise HTTPException(status_code=404, detail={
            "msg": "Неверный код"
        })
    phone_token = security.create_phone_token(data={"sub": phone})
    return {"phone_token": phone_token}





@router.get(
    "/change_phone/{phone}",
    summary="Change phone (make call)",
    response_model=auth_schemas.ResponseSuccess
)
async def create_call_change_phone(
        phone: constr(regex=r"^(\+)[7][0-9]{10}$") = Path(),
        current_user: User = Depends(get_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        logger.info(f"api/endpoints/phone- create_call_change_phone. Доступно только авторизованным пользователям")
        raise HTTPException(
            status_code=400, detail={
                "msg": "Доступно только авторизованным пользователям"
            }
        )

    phone_exist = user_crud.get_user_by_phone(db, phone)
    if phone_exist:
        logger.info(f"api/endpoints/phone- create_call_change_phone. Пользователь с таким номером уже существует")
        raise HTTPException(
            status_code=400, detail={
                "msg": "Пользователь с таким номером уже существует"
            }
        )
    phone_crud.check_phone_blocking(phone, db)

    call_result = phone_utils.call(phone=phone)

    if call_result["result"] == "ok":
        code = call_result["code"]
        phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
        return {"msg": "success"}
    else:
        logger.error(
            f"api/endpoints/phone- create_call_change_phone. Ошибка сервиса звонков: {call_result['error_code']}")
        phone_utils.error_handler(call_result["error_code"])

    # if call_result["success"]:
    #     code = call_result["data"]["code"]
    #
    #     phone_crud.create_phone_call(phone=phone, verification_code=code, db=db)
    #     return {"msg": "success"}
    # else:
    #     phone_utils.error_handler(call_result["error"])


@router.get(
    "/check_phone_code_change/{phone}/{code}",
    summary="Check code to change phone",
    response_model=auth_schemas.ResponseCheckPhoneCode,
    responses={
        404: exception.custom_errors("Bad Request", [{
            "msg": "Неверный код"
        }])
    }
)
async def check_phone_code_change(
        phone: constr(regex=r"^(\+)[7][0-9]{10}$") = Path(),
        code: str = Path(),
        current_user: User = Depends(get_user),
        db: Session = Depends(get_db)
):

    if not current_user:
        logger.info(f"api/endpoints/phone- check_phone_code_change. Доступно только авторизованным пользователям")
        raise HTTPException(
            status_code=400, detail={
                "msg": "Доступно только авторизованным пользователям"
            }
        )

    check_verification_code = phone_crud.check_phone_code(
        db=db,
        phone=phone,
        verification_code=code
    )
    if not check_verification_code:
        logger.info(f"api/endpoints/phone- check_phone_code_change. Неверный код")
        raise HTTPException(status_code=404, detail={
            "msg": "Неверный код"
        })
    phone_token = security.create_phone_token(data={"sub": phone})
    return {"phone_token": phone_token}

