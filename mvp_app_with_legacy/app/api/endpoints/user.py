import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, responses, Form, Header
from pydantic import ValidationError

from sqlalchemy.orm import Session
import random
import string
from app.crud import (
    user as user_crud,
    devices as devices_crud
)
from app.crud.ad import get_paginated_advs
from app.crud.user import add_or_remove_favorites, add_list_favorites, get_current_user_or_none, inc_unique_views, \
    create_cash_wallet, multiply_bonus, create_transaction
from app.db.db_models import User, Ad, favorite_advs, WalletSettings, WalletTransactions, ServicesList
from app.logger import setup_logger
from app.schemas import user as user_schemas, auth as auth_schemas
from app.schemas.ad import PaginatedItems, LocationOutModel, ItemsOutModel
from app.schemas.user import ListAdvsOut, CashWalletOut, DepositOrWithdrawModel, TransactionsResponse
from app.utils import exception
from app.utils.dependencies import get_db
from starlette.responses import JSONResponse

from app.utils.security import decode_withdraw_token, encode_withdraw_token

router = APIRouter(prefix="/user", tags=["User"])
logger = setup_logger(__name__)

@router.get("/me", summary="Get current User",
            response_model=user_schemas.UserOutMe)
async def get_me(current_user: User = Depends(user_crud.get_current_user)):
    """
    Получение авторизованного пользователя.

    Параметры:
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - Объект пользователя
    """

    user_location_out = {}
    if current_user.location:
        user_location_dict = current_user.location.to_dict()
        user_location_out = LocationOutModel(**user_location_dict)

    if current_user.cash_wallet:
        user_cash = current_user.cash_wallet.balance
    else:
        user_cash = 0


    user_out = {
        "id": current_user.id,
        "email": current_user.email,
        "emailVerified": current_user.emailVerified,
        "phone": current_user.phone,
        "phoneVerified": current_user.phoneVerified,
        "name": current_user.name,
        "rating": current_user.rating,
        "balance":user_cash,
        "unread_messages": current_user.unread_messages,
        "feedback_count": current_user.feedback_count,
        "subscriptions_count": len(current_user.subscriptions),
        "subscribers_count": len(current_user.subscribers),
        "photo": current_user.photo,
        "googleId": current_user.googleId,
        "appleId": current_user.appleId,
        "is_active": current_user.is_active,
        "is_blocked": current_user.is_blocked,
        "createdAt": current_user.createdAt,
        "updatedAt": current_user.updatedAt,
        "lastLoginAt": current_user.lastLoginAt,
        "location": user_location_out
    }

    return user_out


@router.get(
    "/{user_id}",
    summary="Read single User",
    response_model=user_schemas.UserMiniCardOut
)
async def read_user_by_id(
        user_id: int,
        device_id: str = Header(default=None),
        current_user: User = Depends(user_crud.get_current_user_or_none),
        db: Session = Depends(get_db)
):
    """
    Получение пользователя по идентификатору.

    Параметры:
    - user_id: Идентификатор пользователя.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Объект пользователя
    """

    db_user = user_crud.get_user_by_id(db, user_id=user_id)
    if not db_user:
        logger.error(f"api/endpoints/user- read_user_by_id. Пользователь не найден. user_id: {user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    if not db_user.is_active:
        db_user.phone = None

    # GET "Device-Id" header from request name it as "device_id"
    if device_id:  # IF device_id is not None ===>
        await inc_unique_views(current_user, device_id, user_id, db_user, db)

    db_user.subscriptions_count = len(db_user.subscriptions)
    db_user.subscribers_count = len(db_user.subscribers)

    return db_user


@router.post(
    "/upload-photo",
    summary="Upload User photo",
    status_code=202
)
async def create_upload_file(
        photo: UploadFile = File(),
        current_user=Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    """
    Загрузка аватарки пользователя.

    Параметры:
    - photo: Изображение (form-data).
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - info: "file 'Имя файла' saved at 'Путь файла'"
    """

    result = await user_crud.upload_user_photo(photo, current_user.id, db)

    if result:
        return JSONResponse(status_code=202, content={"detail": "Image uploaded successfully"})
    else:
        logger.error(f"api/endpoints/user- create_upload_file. Аватарка не загружена. user_id: {current_user.id}")
        return JSONResponse(status_code=400, content={"detail": "Image NOT uploaded, try again"})
        # raise HTTPException(status_code=400, detail="")


@router.post(
    "/change-password",
    summary="Change User password",
    status_code=200,
    response_model=auth_schemas.ResponseSuccess,
    responses={
        400: exception.custom_errors("Bad Request", [{
            "msg": "Неверный пароль"
        }]),
        403: exception.custom_errors("Bad Request", [{
            "msg": "Ошибка валидации пароля"
        }])
    }
)
async def change_password(
        data: user_schemas.UserChangePassword,
        current_user: user_schemas.UserId = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    """
    Изменение пароля авторизованного пользователя.

    Параметры:
    - current_password: Текущий пароль.
    - new_password: Новый пароль.
    - token: Токен авторизации.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - msg: success/Ошибка валидации пароля/Неверный пароль
    """

    user = user_crud.get_user_by_id(db, current_user.id)
    try:
        passwords_valid = user_schemas.UserChangePasswordValidation(
            **data.dict())
    except ValidationError:
        raise HTTPException(status_code=403, detail={
            "msg": "Ошибка валидации пароля"
        })
    res = user_crud.change_password_manually(
        user,
        passwords_valid.current_password,
        passwords_valid.new_password,
        db)
    if not res:
        raise HTTPException(status_code=400, detail={
            "msg": "Неверный пароль"
        })
    devices_crud.delete_user_devices_except_current(data.token, user, db)
    return {"msg": "success"}


# Получение активных(опубликованных) объявлений по идентификатору пользователя
@router.get("/{user_id}/published", summary="Get User's published advs", status_code=200,
            response_model=PaginatedItems)
async def get_user_card_published(
        user_id: int,
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        current_user: Optional[User] = Depends(get_current_user_or_none),
        db: Session = Depends(get_db)
):
    """
    Получение опубликованных объявлений выбранного пользователя

    Параметры:
    - user_id: Идентификатор выбранного пользователя.
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список опубликованных объявлений
    """
    auth_user_id = current_user.id if current_user else None
    # Получаем модель пользователя по идентификатору
    db_user = user_crud.get_user_by_id(db, user_id=user_id)
    # Если не нашли - пишем ошибку
    if not db_user:
        logger.error(f"api/endpoints/user- get_user_card_published. Пользователь на найден. user_id: {db_user.id}")
        raise HTTPException(status_code=404, detail="User not found")

    # Устанавливаем пустую категорию, статус=3(publish) и тип выборки = card(карточка пользователя)
    category = None
    status = 3
    query_type = 'card'

    # Устанавливаем пустые фильтры
    filters = None
    price_from = None
    price_to = None
    location = None

    search = None
    radius = None
    # Вызываем функцию выдачи объявлений с нужными параметрами
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, db_user.id, filters, price_from,
                                 price_to, location, search, radius, auth_user_id=auth_user_id)

    return ad_list


# Получение архивных(завершенных) объявлений по идентификатору пользователя
@router.get("/{user_id}/archived", summary="Get User's archived advs", status_code=200,
            response_model=PaginatedItems)
async def get_user_card_archived(
        user_id: int,
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        current_user: Optional[User] = Depends(get_current_user_or_none),
        db: Session = Depends(get_db)
):
    """
    Получение архивных объявлений выбранного пользователя

    Параметры:
    - user_id: Идентификатор выбранного пользователя.
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список архивных объявлений
    """
    auth_user_id = current_user.id if current_user else None
    # Получаем модель пользователя по идентификатору
    db_user = user_crud.get_user_by_id(db, user_id=user_id)
    # Если не нашли - пишем ошибку
    if not db_user:
        logger.error(f"api/endpoints/user- get_user_card_archived. Пользователь на найден. user_id: {db_user.id}")
        raise HTTPException(status_code=404, detail="User not found")

    # Устанавливаем пустую категорию, статус=4(archive) и тип выборки = card(карточка пользователя)
    category = None
    status = 4
    query_type = 'card'

    # Устанавливаем пустые фильтры
    filters = None
    price_from = None
    price_to = None
    location = None

    search = None
    radius = None
    # Вызываем функцию выдачи объявлений с нужными параметрами
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, db_user.id, filters, price_from,
                                 price_to, location, search, radius, auth_user_id=auth_user_id)

    return ad_list


@router.delete("/deactivate", summary="Deactivate User", status_code=200)
async def deactivate_user(
        current_user: user_schemas.UserId = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    """
    Удаление авторизованного пользователя (деактивация)

    Параметры:
    - current_user (User): Объект авторизованного пользователя.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Идентификатор удаленного пользователя {"deactivated": user.id}
    """

    user = user_crud.get_user_by_id(db, current_user.id)

    if user:
        user_url = f"./files{user.photo.url}/"
        # Удаляем связанную запись UserPhoto, если она есть
        if user.photo:
            db.delete(user.photo)

        if os.path.exists(user_url):
            shutil.rmtree(os.path.dirname(user_url))

        # Удаляем связанную запись UserLocation, если она есть
        if user.location:
            db.delete(user.location)

        # Удаляем связанные записи UserDevices
        for device in user.device:
            db.delete(device)

        for ad in user.ads:
            ad.status_id = 4

        characters = string.ascii_letters + string.digits
        unique_characters = random.sample(characters, len(characters))
        random_string = ''.join(random.choices(unique_characters, k=50))

        user.email = None
        user.emailVerified = False
        user.phone = random_string
        user.phoneVerified = False

        user.googleId = random_string
        user.appleId = random_string
        user.name = 'Пользователь удален'
        user.rating = None
        user.password = random_string

        user.is_active = False

        # Подтверждаем транзакцию
        db.commit()
    else:
        logger.error(f"api/endpoints/user- deactivate_user. Пользователь на найден. user_id: {current_user.id}")
        raise HTTPException(status_code=400, detail='User not found')

    return {"deactivated": user.id}


@router.get("/image/{uuid}", summary="Get Image By UUID", response_class=responses.FileResponse)
async def get_user_image(uuid: UUID, db: Session = Depends(get_db)):
    """
    Получение изображения по разрешению и идентификатору.

    Параметры:
    - resolution: Резрешение изображения.
    - uuid: Идентификатор изображения.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Изображение, как файл .webp
    """

    resolution = '300x300'
    db_photo = user_crud.get_user_image_by_uuid(db=db, image_uuid=uuid)
    # Если фото не найдено, выводим ошибку
    if not db_photo:
        logger.error(f"api/endpoints/user- get_user_image. Фото на найдено в БД")
        raise HTTPException(404)
    # Формируем путь(ссылку) для выдачи изображения
    image = f"./files{db_photo.url}/{resolution}.webp"
    # Если в данной директории нет файла, выводим ошибку
    if not Path(image).is_file():
        logger.error(f"api/endpoints/user- get_user_image. Фото на найдено в хранилище")
        raise HTTPException(404)
    return image


@router.patch(
    "/edit",
    summary="Change Users data by Identifier"
)
async def edit_user_data_by_id(
        name: Optional[str] = Form(None),
        location: Optional[str] = Form(None),
        photo: Optional[UploadFile] = File(None),
        delete_photo: Optional[bool] = Form(None),
        current_user: user_schemas.UserId = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    """
    Изменение пользователя по идентификатору (Имя и Фото).

    Параметры:
    - key: Идентификатор пользователя.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - users: Список идентификаторов пользователей, у которых изменился статус.
    - errors: Список идентификаторов пользователей, у которых НЕ изменился статус.
    """

    response_name, response_location, user_photo = await user_crud.edit_user_data(current_user.id, name, location,
                                                                                  photo, delete_photo, db)
    # return response_name, response_location, user_photo
    return {"name": response_name, "location": response_location, "photo": user_photo}


@router.post('/favorite/{adv_id}', summary="Add/remove adv to/from favorites", status_code=202)
async def add_or_remove_favorite_advs_to_user(
        adv_id: UUID,
        current_user: User = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    result = await add_or_remove_favorites(current_user.id, adv_id, db)
    return result


@router.get("/favorite/get", summary="Get User's favorite advs", status_code=200,
            response_model=PaginatedItems)
async def get_all_favorite_advs_of_user(
        # sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        current_user: User = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    """
    Получение избранных объявлений авторизованного пользователя с пагинацией.

    Параметры:
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на странице.
    - current_user: Авторизованный пользователь.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список избранных объявлений
    """

    # Если не нашли - пишем ошибку
    if not current_user:
        logger.error(f"api/endpoints/user- get_all_favorite_advs_of_user. Пользователь не найден")
        raise HTTPException(status_code=404, detail="User not found")

    # Запрос для получения избранных объявлений, отсортированных по дате создания
    # favorite_ads = db.query(Ad).join(User.favorite_advs).filter(User.id == current_user.id)

    # if sort == "date_desc":
    #     favorite_ads = favorite_ads.order_by(favorite_ads.created_at.desc())
    # elif sort == "date_asc":
    #     favorite_ads = favorite_ads.order_by(favorite_ads.created_at)

    # Получаем общее количество избранных объявлений
    # total = favorite_ads.count()
    # # Вычисляем смещение
    # offset = (page - 1) * limit
    # favorite_ads = favorite_ads.offset(offset).limit(limit).all()

    favorite_ads = (
        db.query(Ad)
        .join(favorite_advs, Ad.id == favorite_advs.c.ad_id)
        .filter(favorite_advs.c.user_id == current_user.id)
        .order_by(favorite_advs.c.created_at.desc())
    )

    total = favorite_ads.count()
    offset = (page - 1) * limit
    favorite_ads = favorite_ads.offset(offset).limit(limit).all()

    ad_list = []
    for ad in favorite_ads:
        photos = ad.photos[0].id if ad.photos else ''
        favorite = current_user.id in [user.id for user in ad.favorited_by]
        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict(),
            photos=photos,
            favorite=favorite,
            status=ad.status.status,
            created_at=str(ad.created_at)
        )
        ad_list.append(ad_out)

    return PaginatedItems(total=total, items=ad_list)


@router.post('/favorite_list', summary="Add list of advs to favorites", status_code=202)
async def add_favorite_advs_to_user_by_list(
        ad_list: List[UUID],
        current_user: User = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    result = await add_list_favorites(current_user.id, ad_list, db)
    return result


@router.post("/favorite_list/get", summary="Get favorite advs by list", status_code=200,
             response_model=PaginatedItems)
async def get_all_favorite_advs_of_user(
        request_data: ListAdvsOut,
        db: Session = Depends(get_db)
):
    """
    Получение избранных объявлений по списку идентификаторов с пагинацией.

    Параметры:
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список объявлений
    """
    ad_list = request_data.ad_list
    page = request_data.page
    limit = request_data.limit

    query = db.query(Ad).filter(
        Ad.id.in_(ad_list)
    )

    total = query.count()
    offset = (page - 1) * limit
    advs = query.offset(offset).limit(limit).all()

    adv_list = []
    for ad in advs:
        photos = ad.photos[0].id if ad.photos else ''
        favorite = True
        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict(),
            photos=photos,
            favorite=favorite,
            status=ad.status.status,
            created_at=str(ad.created_at)
        )
        adv_list.append(ad_out)

    return PaginatedItems(total=total, items=adv_list)


@router.post('/request_contact/{user_id}', summary="Increment users contact request", status_code=200)
async def increment_users_contact_request(
        user_id: int,
        db: Session = Depends(get_db)
):
    try:
        user = user_crud.get_user_by_id(db, user_id)
        user.contact_requests += 1
        db.commit()
        db.refresh(user)
        return user.contact_requests

    except Exception as e:
        logger.error(f"api/endpoints/user- increment_users_contact_request. Ошибка: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка, попробуйте еще раз")


@router.get("/wallet/get", summary="Get current Users wallets")
async def get_users_wallet(current_user: User = Depends(user_crud.get_current_user), db: Session = Depends(get_db)):
    """
    Получение Кошелька авторизованного пользователя.

    Параметры:
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - id: Идентификатор кошелька
    - user_id: Идентификатор пользователя
    - balance: Баланс счета
    """

    # Если кошелек существует, то выдаем значение баланса. Иначе выдаем `0`
    if current_user.cash_wallet:
        user_cash = current_user.cash_wallet.balance
    else:
        user_cash = 0

    wallet_out = CashWalletOut(
        id=current_user.cash_wallet.id,
        user_id=current_user.id,
        balance=user_cash
    )

    return wallet_out


@router.post("/wallet/deposit/cash", summary="Deposit current Users cash wallet")
async def deposit_users_cash_wallet(cash: DepositOrWithdrawModel, current_user: User = Depends(user_crud.get_current_user),
                                    db: Session = Depends(get_db)):
    """
    Пополнение Кошелька авторизованного пользователя.

    Параметры:
    - current_user (User): Объект авторизованного пользователя.
    - cash (DepositModel): Сумма пополнения кошелька
    Возвращает:
    - id: Идентификатор кошелька
    - user_id: Идентификатор пользователя
    - balance: Баланс счета
    """

    # Получение значений minimal_deposit и multiplier
    wallet_settings = db.query(WalletSettings).first()

    if wallet_settings:
        minimal_deposit = wallet_settings.minimal_deposit
        cash_multiplier = wallet_settings.multiplier
    else:
        minimal_deposit = 100
        cash_multiplier = 1

    if cash.amount < minimal_deposit:
        logger.error(f"api/endpoints/user- deposit_users_cash_wallet. Пополнение должно быть больше {minimal_deposit}")
        raise HTTPException(status_code=400, detail=f"Deposit must be {minimal_deposit} or more")

    # Если у пользователя еще нет кошелька
    if not current_user.cash_wallet:
        balance_to_deposit = multiply_bonus(cash.amount, cash_multiplier)
        cash_wallet = create_cash_wallet(current_user.id, balance_to_deposit, db)

    # Если у пользователя уже есть кошелек
    else:
        # Увеличиваем баланс кошелька в копейках на размер суммы пополнения
        cash_wallet = current_user.cash_wallet

        balance_to_deposit = multiply_bonus(cash.amount, cash_multiplier)
        cash_wallet.balance += balance_to_deposit

        db.commit()

    # Данные для записи Транзакции
    cash_sign = True
    service = "Пополнение кошелька"
    deposit = cash.amount
    # Создаем запись Транзакции
    transaction_out = create_transaction(current_user.id, cash_wallet.id, balance_to_deposit, cash_sign, service, deposit, db)

    wallet_out = CashWalletOut(
        id=cash_wallet.id,
        user_id=cash_wallet.user_id,
        balance=cash_wallet.balance
    )

    response = {
        "wallet": wallet_out,
        "transaction": transaction_out
    }

    return response


@router.post("/wallet/withdraw/cash", summary="Withdraw current Users cash wallet")
async def withdraw_users_cash_wallet(
        cash: DepositOrWithdrawModel,
        transaction_token: str = Header(...),
        current_user: User = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)):
    """
    Списание с Кошелька авторизованного пользователя.

    Параметры:
    - current_user (User): Объект авторизованного пользователя.
    - cash (DepositModel): Сумма пополнения кошелька
    Возвращает:
    - wallet: Объект кошелька пользователя
    - transaction: Объект транзакции
    """

    token = encode_withdraw_token(cash.service_id, cash.amount, current_user.id)

    decoded_data = decode_withdraw_token(transaction_token)
    if (not decoded_data) or (current_user.id != decoded_data["user_id"]) or (cash.amount != decoded_data["amount"]):
        logger.error(f"api/endpoints/user- withdraw_users_cash_wallet. Покупка не авторизована. user_id: {current_user.id}")
        raise HTTPException(status_code=400, detail="Покупка не авторизована")

    query = db.query(ServicesList).get(decoded_data["service_id"])
    if not query:
        logger.error(
            f"api/endpoints/user- withdraw_users_cash_wallet. Покупка не авторизована. Не найдена услуга. user_id: {current_user.id}")
        raise HTTPException(status_code=400, detail="Покупка не авторизована")

    # Если у пользователя еще нет кошелька
    if not current_user.cash_wallet:
        logger.error(f"api/endpoints/user- withdraw_users_cash_wallet. Ошибка. Не найден кошелек. user_id: {current_user.id}")
        raise HTTPException(status_code=400, detail="Ошибка, недостаточно средств")

    # Если у пользователя уже есть кошелек
    else:
        cash_wallet = current_user.cash_wallet

        if cash_wallet.balance < query.cost:
            logger.error(
                f"api/endpoints/user- withdraw_users_cash_wallet. Ошибка, недостаточно средств. user_id: {current_user.id}")
            raise HTTPException(status_code=400, detail="Ошибка, недостаточно средств")

        # Уменьшаем баланс кошелька на размер суммы списания
        cash_wallet.balance -= query.cost
        db.commit()

        # Данные для записи Транзакции
        cash_sign = False
        service = query.service
        deposit = None
        # Создаем запись Транзакции
        transaction_out = create_transaction(current_user.id, cash_wallet.id, query.cost, cash_sign, service, deposit, db)

        wallet_out = CashWalletOut(
            id=cash_wallet.id,
            user_id=cash_wallet.user_id,
            balance=cash_wallet.balance
        )

        response = {
            "wallet": wallet_out,
            "transaction": transaction_out
        }

    return response


@router.get("/wallet/transactions", summary="Get All Users Transactions")
async def get_users_transactions(
        sort: str = "date_desc",
        # page: int = 1,
        # limit: int = Query(default=50, lte=100),
        start_date: str = None,
        end_date: str = None,
        current_user: User = Depends(user_crud.get_current_user),
        db: Session = Depends(get_db)
):
    """
    Получение всех транзакций пользователя

    Параметры:
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - transactions: Все транзакции пользователя
    """

    # Определяем порядок сортировки в зависимости от параметра sort
    if sort == "date_asc":
        order_by_clause = WalletTransactions.created_at.asc()
    else:
        order_by_clause = WalletTransactions.created_at.desc()  # По умолчанию сортируем по убыванию даты

    # Запрос к базе данных с учетом сортировки, фильтрации по дате и пагинации
    query = db.query(WalletTransactions).filter(WalletTransactions.user_id == current_user.id)

    if query:
        if start_date and end_date:
            # Преобразование начальной даты к началу дня
            start_date_1 = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            # Преобразование конечной даты к концу дня
            end_date_1 = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)

            query = query.filter(WalletTransactions.created_at >= start_date_1)
            query = query.filter(WalletTransactions.created_at <= end_date_1)

        transactions = (
            query
            .order_by(order_by_clause)
            # .offset((page - 1) * limit)
            # .limit(limit)
            .all()
        )
        # total = query.count()

        formatted_transactions = [
            WalletTransactions(
                id=t.id,
                cash=t.cash,
                deposit=t.deposit,
                cash_sign=t.cash_sign,
                service=t.service,
                created_at=t.created_at
            )
            for t in transactions
        ]

    else:
        formatted_transactions = []

    response = {
        "balance": current_user.cash_wallet.balance if current_user.cash_wallet else 0,
        # "total": total,
        "transactions": formatted_transactions
    }

    return response


@router.get("/wallet/settings", summary="Get Minimal Deposit")
async def get_wallet_settings(current_user: User = Depends(user_crud.get_current_user), db: Session = Depends(get_db)):
    """
    Получение минимальной суммы пополнения кошелька

    Параметры:
    - current_user (User): Объект авторизованного пользователя.

    Возвращает:
    - minimal_deposit: Минимальная сумма пополнения кошелька
    - multiplier: Коеффициент кэшбека для пополнения кошелька
    """

    # Получение значений minimal_deposit и multiplier
    wallet_settings = db.query(WalletSettings).first()

    if wallet_settings:
        minimal_deposit = wallet_settings.minimal_deposit
        multiplier = wallet_settings.multiplier
    else:
        minimal_deposit = 100
        multiplier = 1

    response = {
        "minimal_deposit": minimal_deposit,
        "multiplier": multiplier
    }
    return response


@router.get("/wallet/services/get", summary="Withdraw current Users cash wallet")
async def get_wallet_services(
        current_user: User = Depends(user_crud.get_current_user),  # ToDo: Is only authorized ?
        db: Session = Depends(get_db)):

    services_list = db.query(ServicesList).all()
    return services_list
