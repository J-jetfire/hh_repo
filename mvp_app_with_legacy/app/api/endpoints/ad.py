import ast
import json
from typing import List, Optional, Dict, Union

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException, Query, Body, Header
from uuid import UUID

from sqlalchemy.sql.expression import or_
from sqlalchemy.orm import Session
from starlette.background import BackgroundTasks
# from fastapi_cache.decorator import cache
from app.crud.catalog import get_all_fields
# from app.main import logger
from app.utils.dependencies import get_db
from app.db.db_models import Ad, User, Catalog, AdditionalFields
from app.crud.user import get_current_user as get_user, get_current_user_or_none
from app.crud.ad import publish_adv, delete_old_images, edit_adv, change_status_adv, \
    get_paginated_advs, get_adv_data, get_adv_out, inc_adv_unique_views
from app.schemas.ad import AdOutModel, ItemsOutModel, AdCatalogOutModel, \
    PaginatedItems, ChangeAdStatusModel, AddOrEditAdvModel, AdvAndCatalogModel
from app.utils.ad import validate_ad, validate_photos
from app.logger import setup_logger
# from app.utils.redis import custom_key_builder

logger = setup_logger(__name__)

router = APIRouter(prefix="/items", tags=["Advertisements"])


# Получение всех объявлений с учетом фильтров, сортировки и поиска
@router.post('', summary="Get all Advertisements by filters", status_code=200, response_model=PaginatedItems)
async def get_all_ads_by_filters(
        req: Request,
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_or_none)
):
    """
    Получение объявлений с применением сортировки, пагинации и фильтров.

    Параметры:
    - request: Тело запроса.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя (если авторизован)

    Возвращает:
    - PaginatedItems:
        - total: Кол-во объявлений.
        - items: Список объявлений.
    """

    try:
        json_body = await req.json()
    except:
        json_body = {}
    category = json_body.get('category', None)
    price_from = json_body.get('price_from', None)
    price_to = json_body.get('price_to', None)
    sort = json_body.get('sort', 'date_desc')
    page = json_body.get('page', 1)
    limit = json_body.get('limit', 50)
    filters = json_body.get('filters', None)
    location = json_body.get('location', None)
    radius = json_body.get('radius', None)
    search = json_body.get('search', None)

    # Проверка, является ли юзер авторизованным и устанавливаем тип запроса в зависимости от результата проверки
    if current_user is not None:
        user_id = current_user.id
        query_type = 'all_user_category' if category else 'all_user_no_category'
    else:
        user_id = 0
        query_type = 'all_no_user_category' if category else 'all_no_user_no_category'

    status = 3 # Ставим статус=3(publish)
    # Вызываем функцию получения объявлений
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, user_id, filters, price_from, price_to, location, search, radius, auth_user_id=user_id)
    return ad_list


# Маршрут для получения всех моделей Ad
@router.get('', summary="Get all Advertisements", status_code=200, response_model=PaginatedItems)
async def get_all_ads(
        category: Optional[UUID] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        filters: Dict[str, Union[str, List[str]]] = Body(None),  # Обновлено
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_or_none)
):
    """
    Получение объявлений с применением сортировки, пагинации и фильтров.

    Параметры:
    - category: Фильтр категории.
    - price_from: Фильтр цены => от.
    - price_to: Фильтр цены => до.
    - sort: Сортировка.
    - page: Страница пагинации.
    - limit: Кол-во объявлений на одной странице.
    - filters: Фильтры доп.полей.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя (если авторизован)

    Возвращает:
    - PaginatedItems:
        - total: Кол-во объявлений.
        - items: Список объявлений.
    """
    status = 3
    location = {}
    if current_user is not None:
        user_id = current_user.id
        query_type = 'all_user_category' if category else 'all_user_no_category'
    else:
        user_id = 0
        query_type = 'all_no_user_category' if category else 'all_no_user_no_category'
    search = None
    radius = None
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, user_id, filters, price_from, price_to, location, search, radius, auth_user_id=user_id)

    return ad_list


# Маршрут для получения модели объявления и Каталога по id объявления для редактирования
@router.get('/catalog/{key}', summary="Get Ad and Catalog by Advertisement identifier", status_code=200, response_model=AdvAndCatalogModel)
async def get_catalog_from_ad(key: UUID, db=Depends(get_db)):
    """
    Получение объявления и связанного объекта каталога.

    Параметры:
    - key: Идентификатор объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - AdvAndCatalogModel:
        - ad_info: Объект объявления.
        - catalog_info: Объект каталога с доп.полями.
    """

    ad = db.query(Ad).get(key)

    if ad:
        communication = {
            "phone": ad.contact_by_phone,
            "message": ad.contact_by_message
        }

        fields = {}

        catalogs = db.query(Catalog).filter(Catalog.id == ad.catalog_id).outerjoin(AdditionalFields).filter(
            or_(AdditionalFields.parent_id != None, AdditionalFields.parent_id == None)).all()
        additional_fields = catalogs[0].additional_fields
        if ad.fields:
            for field in ad.fields:
                matching_field = next((item for item in additional_fields if item.alias == field.key), None)
                if matching_field:
                    try:
                        field_value_list = ast.literal_eval(field.value)
                        if (type(field_value_list) != list) and (type(field_value_list) != bool):
                            field_value_list = str(field_value_list)

                        fields[matching_field.alias] = field_value_list
                    except (SyntaxError, ValueError):
                        value = field.value.lower()
                        fields[matching_field.alias] = True if value == "true" else False if value == "false" else str(
                            field.value)
        if ad.photos:
            photos = [photo.id for photo in ad.photos]
        else:
            photos = []

        ad_out = AdCatalogOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict() if ad.location else {},
            communication=communication,
            fields=fields,
            photos=photos
        )
    else:
        logger.error(f"api/endpoints/ad. get_catalog_from_ad. Объявление не найдено: {key}")
        raise HTTPException(status_code=404, detail='Объявление не найдено')

    try:
        # ad = db.query(Ad).get(key)
        catalog = ad.catalog
        catalog_info = get_all_fields(catalog.id, db)
    except:
        logger.error(f"api/endpoints/ad. get_catalog_from_ad. Данные каталога не найдены: {key}")
        raise HTTPException(status_code=404, detail='Данные каталога не найдены')

    result = {
        "ad_info": ad_out,
        "catalog_info": catalog_info
    }

    return result


# Эндпоинт получения опубликованных объявлений авторизованного пользователя
@router.get('/user/published', summary="Get User's published Advertisements", status_code=200,
            response_model=PaginatedItems)
async def get_user_ads_published(
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_user)
):
    """
    Получение объявлений авторизованного пользователя со статусом "Опубликовано".

    Параметры:
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на одной странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user: Объект авторизованного пользователя.

    Возвращает:
    - PaginatedItems: Общее кол-во объявлений и список объявлений на выбранной странице.
    """

    category = None
    status = 3
    query_type = 'card'

    filters = None
    price_from = None
    price_to = None
    location = None
    search = None
    radius = None
    user_id = current_user.id if current_user is not None else None
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, current_user.id, filters, price_from, price_to, location, search, radius, auth_user_id=user_id)

    return ad_list


# Эндпоинт получения ждущих действий объявлений авторизованного пользователя
@router.get('/user/waiting', summary="Get User's waiting Advertisements", status_code=200,
            response_model=PaginatedItems)
async def get_user_ads_waiting(
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_user)
):
    """
    Получение объявлений авторизованного пользователя со статусом "Ждут действия".

    Параметры:
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на одной странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user: Объект авторизованного пользователя.

    Возвращает:
    - PaginatedItems: Общее кол-во объявлений и список объявлений на выбранной странице.
    """

    category = None
    status = 2
    query_type = 'card'

    filters = None
    price_from = None
    price_to = None
    location = None
    search = None
    radius = None
    user_id = current_user.id if current_user is not None else None
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, current_user.id, filters, price_from, price_to, location, search, radius, auth_user_id=user_id)

    return ad_list


# Эндпоинт получения архивированных(завершенных) объявлений авторизованного пользователя
@router.get('/user/archived', summary="Get User's archived Advertisements", status_code=200,
            response_model=PaginatedItems)
async def get_user_ads_archived(
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_user)
):
    """
    Получение объявлений авторизованного пользователя со статусом "Архивировано".

    Параметры:
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во объявлений на одной странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user: Объект авторизованного пользователя.

    Возвращает:
    - PaginatedItems: Общее кол-во объявлений и список объявлений на выбранной странице.
    """

    category = None
    status = 4
    query_type = 'card'

    filters = None
    price_from = None
    price_to = None
    location = None
    search = None
    radius = None
    user_id = current_user.id if current_user is not None else None
    ad_list = get_paginated_advs(query_type, category, sort, page, limit, status, db, current_user.id, filters, price_from, price_to, location, search, radius, auth_user_id=user_id)

    return ad_list


# Эндпоинт получения объявления по идентификатору
@router.get('/{key}', summary="Get Advertisement by identifier", status_code=200, response_model=AdOutModel)
async def get_advertisement_by_id(key: UUID, device_id: str = Header(default=None), db=Depends(get_db), current_user: Optional[User] = Depends(get_current_user_or_none)):
    """
    Публикация объявления по идентификатору каталога. Доступно только для авторизованных пользователей.

    Параметры:
    - key (UUID): Идентификатор объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - AdOutModel: Объект объявления.
    """

    ad = get_adv_data(key, db)

    if current_user:
        user_id = current_user.id
    else:
        user_id = None

    if ad:
        if device_id:
            await inc_adv_unique_views(user_id, device_id, ad, db)

        ad_out = get_adv_out(ad, user_id, db)
        return ad_out
    else:
        logger.error(f"api/endpoints/ad. get_advertisement_by_id. Объявление не найдено: {key}")
        raise HTTPException(status_code=404, detail='Ad not found')


# Эндпоинт публикации объявления по идентификатору категории
@router.post("/publish/{key}", summary="Add new Advertisement", status_code=201, response_model=AddOrEditAdvModel)
async def add_advertisement(background_tasks: BackgroundTasks,
                            key: UUID,
                            request: Request,
                            photos: List[UploadFile] = File(...),
                            db: Session = Depends(get_db),
                            current_user: User = Depends(get_user)):
    """
    Публикация объявления по идентификатору каталога. Доступно только для авторизованных пользователей.

    Параметры:
    - key (UUID): Идентификатор объявления.
    - request: Тело запроса (form-data).
    - photos: Изображения (form-data).
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(только для Авторизованных).

    Возвращает:
    - id: Идентификатор объявления.
    """

    if not photos:
        logger.error(f"api/endpoints/ad. add_advertisement. Нет фотографий")
        raise HTTPException(status_code=400, detail='Нет фотографий')

    if len(photos) > 20:
        logger.error(f"api/endpoints/ad. add_advertisement. Разрешено не более 20 фотографий")
        raise HTTPException(status_code=400, detail='Разрешено не более 20 фотографий')

    try:
        form_data = await request.form()
    except Exception as e:
        print("Ошибка при получении данных из формы:", str(e))
        logger.error(f"api/endpoints/ad. add_advertisement. Ошибка при получении данных из формы: {str(e)}")
        raise HTTPException(status_code=400, detail="Ошибка при получении данных из формы")

    validate_photos(photos)
    validate_ad(key, form_data, db)

    try:
        user_id = current_user.id

        try:
            logger.info("Запрос на создание объявления принят")
            # item_id = publish_adv(background_tasks, user_id, key, form_data, photos, db)
            item_id = publish_adv(background_tasks, user_id, key, form_data, photos, db)
            return {"id": item_id}
        except Exception as e:
            # Обработка исключения при вызове функции publish_adv
            print("Ошибка при вызове функции publish_adv:", str(e))
            logger.error(f"api/endpoints/ad. add_advertisement. Ошибка при вызове функции publish_adv: {str(e)}")
            return {"message": "Ошибка создания объявления"}

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше
    except Exception as e:
        # Обработка исключения при получении значения user_id
        print("Ошибка при получении user_id:", str(e))
        logger.error(f"api/endpoints/ad. add_advertisement. Ошибка при получении user_id: {str(e)}")
        return {"message": "Ошибка авторизации"}


# Эндпоинт редактирования объявления по идентификатору
@router.patch("/edit/{key}", summary="Edit Advertisement by ID", status_code=200)
async def edit_advertisement(background_tasks: BackgroundTasks,
                             key: UUID,
                             request: Request,
                             new_photos: Optional[List[UploadFile]] = File(None),
                             current_user: User = Depends(get_user),
                             db: Session = Depends(get_db)):
    """
    Редактирование объявления по идентификатору. Доступно только для владельца объявления.

    Параметры:
    - key (UUID): Идентификатор объявления.
    - request: Тело запроса (form-data).
    - new_photos: Новые изображения (form-data).
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(только для Авторизованных).

    Возвращает:
    - id: Идентификатор объявления.
    """

    try:
        form_data = await request.form()

        if "old_photos" in form_data:
            try:
                old_photos = json.loads(form_data.get("old_photos"))
            except:
                old_photos = []
        else:
            logger.error(f"api/endpoints/ad. edit_advertisement. Клиент не передал old_photos: {key}")
            raise HTTPException(status_code=400) # rework exception

        count_old = len(old_photos)
        if new_photos:
            count_new = len(new_photos)
        else:
            count_new = 0
            new_photos = []

        # Проверяем, не пустой ли объект с фото
        if count_new and not new_photos[0].content_type:
            count_new = 0

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше
    except Exception as e:
        # Обработка исключения при получении данных из формы
        print("Ошибка при получении данных из формы:", str(e))
        logger.error(f"api/endpoints/ad. edit_advertisement. Ошибка при получении данных из формы: {key} => {str(e)}")
        raise HTTPException(status_code=400, detail="Ошибка при получении данных из формы")

    if count_old + count_new > 20:
        logger.error(f"api/endpoints/ad. edit_advertisement. Разрешено не более 20 фотографий: {key}")
        raise HTTPException(status_code=400, detail='Разрешено не более 20 фотографий')

    if count_old == 0 and count_new == 0:
        logger.error(f"api/endpoints/ad. edit_advertisement. Должна быть загружена хоть одна фотография: {key}")
        raise HTTPException(status_code=400, detail='Должна быть загружена хоть одна фотография')

    # Удаляем лишние фото, которые убрал из объявления юзер
    # в списке old_photos идентификаторы фото, которые остались
    delete_old_images(old_photos, key, db)
    if count_new > 0:
        validate_photos(new_photos)

    catalog_id = db.query(Ad.catalog_id).filter(Ad.id == key).first()[0]

    try:
        user_id = current_user.id
    except Exception as e:
        # Обработка исключения при получении значения user_id
        print("Ошибка при получении user_id:", str(e))
        return {"message": "Ошибка авторизации"}
    # try to write new_photos to database and server
    # then try to edit another data
    logger.info("Запрос на изменение объявления принят")

    out_type = form_data.get("out_type", None)

    adv_out = edit_adv(background_tasks, catalog_id, key, user_id, form_data, new_photos, out_type, db, old_photos)

    logger.info("Изменение объявления прошло успешно")

    return adv_out


# Эндпоинт изменения статуса объявления на Ждет действия
@router.post("/status_wait/{key}", summary="Change status of Advertisement to waiting", status_code=200, response_model=ChangeAdStatusModel)
async def change_adv_status_wait(key: UUID,
                                 db: Session = Depends(get_db),
                                 current_user: User = Depends(get_user)):
    """
    Изменяет статус объявления на "Ждет действия" по идентификатору, доступно только для владельца объявления.

    Параметры:
    - key (UUID): Идентификатор текущего объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(только Авторизованные).

    Возвращает:
    - status: Changed.
    """

    status = 2
    result = change_status_adv(key, current_user.ads, status, db)

    return result


# Эндпоинт изменения статуса объявления на опубликовано
@router.post("/status_publish/{key}", summary="Change status of Advertisement to published", status_code=200, response_model=ChangeAdStatusModel)
async def change_adv_status_publish(key: UUID,
                                    db: Session = Depends(get_db),
                                    current_user: User = Depends(get_user)):
    """
    Изменяет статус объявления на "Опубликовано" по идентификатору, доступно только для владельца объявления.

    Параметры:
    - key (UUID): Идентификатор текущего объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(только Авторизованные).

    Возвращает:
    - status: Changed.
    """

    status = 3
    result = change_status_adv(key, current_user.ads, status, db)

    return result


# Эндпоинт изменения статуса объявления на Архивировано
@router.post("/status_archive/{key}", summary="Change status of Advertisement to archived", status_code=200, response_model=ChangeAdStatusModel)
async def change_adv_status_archive(key: UUID,
                                    db: Session = Depends(get_db),
                                    current_user: User = Depends(get_user)):
    """
    Изменяет статус объявления на "Архивировано" по идентификатору, доступно только для владельца объявления.

    Параметры:
    - key (UUID): Идентификатор текущего объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(только Авторизованные).

    Возвращает:
    - status: Changed.
    """

    status = 4
    result = change_status_adv(key, current_user.ads, status, db)

    return result


# Эндпоинт изменения статуса объявления на Заблокировано
@router.post("/status_block/{key}", summary="Change status of Advertisement to blocked", status_code=200, response_model=ChangeAdStatusModel)
async def change_adv_status_block(key: UUID,
                                  db: Session = Depends(get_db),
                                  current_user: User = Depends(get_user)):
    """
    Изменяет статус объявления на "Заблокировано" по идентификатору, доступно только для владельца объявления.

    Параметры:
    - key (UUID): Идентификатор текущего объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(только Авторизованные).

    Возвращает:
    - status: Changed.
    """
    status = 5
    result = change_status_adv(key, current_user.ads, status, db)

    return result


# Получение похожих объявлений по идентификатору текущего.
@router.get('/{key}/similar', summary="Get Similar Advertisements", status_code=200, response_model=List[ItemsOutModel])
async def get_similar_advertisements(key: UUID, db=Depends(get_db), current_user: Optional[User] = Depends(get_current_user_or_none)):
    """
    Получение похожих объявлений по идентификатору текущего.

    Параметры:
    - key (UUID): Идентификатор текущего объявления.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя(Авторизован или нет). Optional.

    Возвращает:
    - Список объявлений: до 10 объявлений.
    """

    user_id = current_user.id if current_user else 0
    status = 3  # статус=3(publish)

    # Запрос с выборкой похожих объявлений
    advs = (
        db.query(Ad)
        .filter(
            Ad.id != key,
            Ad.status_id == status,
            Ad.user_id != user_id,
            Ad.catalog_id == db.query(Ad.catalog_id)
            .filter(Ad.id == key, Ad.status_id == status)
            .subquery()
            .as_scalar(),
        )
        .order_by(Ad.created_at.desc())
        .limit(10)
        .all()
    )


    ad_list = []
    for ad in advs:
        if ad.photos:
            photos = ad.photos[0].id
        else:
            photos = ''

        favorite = user_id in [user.id for user in ad.favorited_by]

        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict(),
            photos=photos,
            favorite=favorite,
            status=str(ad.status.status),
            created_at=str(ad.created_at)
        )
        ad_list.append(ad_out)

    return ad_list


@router.get('/{key}/minicard', summary="Get Adv by ID (minicard)", status_code=200, response_model=ItemsOutModel)
async def get_minicard_of_advertisement(key: UUID, db=Depends(get_db)):
    ad = get_adv_data(key, db)
    if ad:
        photos = ad.photos[0].id if ad.photos else ''

        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict() if ad.location else {},
            photos=photos,
            favorite=False,
            status=str(ad.status.status),
            created_at=str(ad.created_at)
        )
        return ad_out

    logger.error(f"api/endpoints/ad. get_minicard_of_advertisement. Объявление не найдено: {key}")
    raise HTTPException(status_code=404, detail="Объявление не найдено")
