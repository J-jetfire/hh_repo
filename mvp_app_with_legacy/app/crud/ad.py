import ast
import json
import os
import shutil
import uuid
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import or_, func, distinct, cast, Integer, Float
from sqlalchemy.sql.expression import and_

from app.core.config import get_current_time2
from app.crud.catalog import get_all_fields
from app.crud.user import check_user_online
from app.logger import setup_logger
from app.schemas.ad import ItemsOutModel, PaginatedItems, AdOutModel, OwnerOutModel
from app.utils.ad import validate_location, get_dynamic_title
from app.utils.additional_fields import validate_fields
from app.utils.image import save_images
from sqlalchemy.orm import Session, aliased, joinedload
from app.db.db_models import Ad, AdStatus, AdPhotos, Location, AdFields, AdvCategories, Catalog, AdditionalFields, User, \
    UserLocation, AdvViews
from app.db.list_constants import LIST_OF_RANGES, FIELDS_LIST
from math import radians

logger = setup_logger(__name__)

# Изменение статуса объявления
def change_post_status(db: Session, post_id: uuid, status_id: int):
    db_post = db.query(Ad).filter(Ad.id == post_id).first()
    db_status = db.query(AdStatus).filter(AdStatus.id == status_id).first()

    if not db_post:
        logger.error(f"crud/ad. change_post_status. Ошибка получения объявления: {post_id} => {status_id}")
        return False
    if not db_status:
        logger.error(f"crud/ad. change_post_status. Ошибка получения статуса объявления: {post_id} => {status_id}")
        return False

    old_status = db_post.status_id
    if old_status == status_id:
        return old_status

    if old_status != 2 and status_id == 3:
        db_post.updated_at = datetime.now()

    db_post.status_id = status_id

    if status_id == 4:
        db_post.archived_at = datetime.now()
    elif status_id == 5:
        db_post.blocked_at = datetime.now()

    db.commit()
    return old_status


# Внесение записей для фотографий объявления
def write_post_images_roads(db: Session, post_id: uuid, images_roads: list):
    images_roads_objects = [AdPhotos(url=x, ad_id=post_id, id=uuid.uuid4()) for x in images_roads]
    db.bulk_save_objects(images_roads_objects)
    db.commit()
    return True


async def write_image_road(db: Session, post_id: uuid, image_road: str, order: int):
    image_road_object = AdPhotos(url=image_road, ad_id=post_id, id=uuid.uuid4(), order=order)
    db.add(image_road_object)
    db.commit()
    return True


# Удаление всех фотографий объявления
def delete_all_images(db: Session, post_id: uuid):
    db.query(AdPhotos).where(AdPhotos.ad_id == post_id).delete()
    db.commit()
    return True


# Удаление фотографий, которых нет в списке (при редактировании объявления, получен список оставшихся фото из запроса)
def delete_old_images(images, ad_id, db):
    try:
        # Собираем все id фотографий, которые нужно удалить
        images_to_delete = [str(adv_image.id) for adv_image in db.query(AdPhotos.id).filter(AdPhotos.ad_id == ad_id).all() if not any(image["id"] == str(adv_image.id) for image in images)]

        # Удаляем все выбранные фотографии и соответствующие директории
        for image_id in images_to_delete:
            adv_image = db.query(AdPhotos).get(image_id)
            if adv_image:
                adv_url = f"./files{adv_image.url}/"
                db.delete(adv_image)
                if os.path.exists(adv_url):
                    shutil.rmtree(os.path.dirname(adv_url))
                # print(f'Deleted directory: {os.path.dirname(adv_url)}')

        # Обновляем порядок
        for adv_image in db.query(AdPhotos).filter(AdPhotos.ad_id == ad_id).all():
            adv_id = str(adv_image.id)
            found = any(image["id"] == adv_id for image in images)
            if found:
                matching_image = next(image for image in images if image["id"] == adv_id)
                new_order = matching_image["order"]
                adv_image.order = new_order
                # print(f'Updated order for {adv_id} - {new_order}')

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"crud/ad. delete_old_images. Ошибка удаления фото из объявления: {ad_id} => {str(e)}")
        print(f'An error occurred: {e}')
        return False
    finally:
        return True


# Публикация объявления
def publish_adv(background_tasks, user_id, key, form_data, photos, db):
    try:
        # Парсинг данных из form-data
        location_data = form_data.get("location")
        location_data = json.loads(location_data)
        fields = form_data.get("fields")
        fields = json.loads(fields)
        description = form_data.get("description")
        price = form_data.get("price")

        communication = form_data.get("communication")
        communication = json.loads(communication)
        contact_by_phone = communication['phone']
        contact_by_message = communication['message']

    except Exception as e:
        # Обработка исключения при загрузке и преобразовании данных местоположения и полей
        print("Ошибка при загрузке и преобразовании данных:", str(e))
        logger.error(f"crud/ad. publish_adv. Ошибка при загрузке и преобразовании данных: {key} => {str(e)}")
        return

    # Пробуем получить динамический заголовок объявления(если есть такой параметр в каталоге)
    dynamic_title = get_dynamic_title(key, fields, db)
    title = dynamic_title if dynamic_title else form_data.get("title").strip()
    description = description.strip()
    # Создание новой записи объявления
    ad = Ad(
        user_id=user_id,
        catalog_id=key,
        title=title,
        description=description,
        price=price,
        contact_by_phone=contact_by_phone,
        contact_by_message=contact_by_message,
        status_id=1,  # Статус изначально черновик - draft
        created_at=datetime.now()
    )

    # Добавляем модель местоположения к объявлению
    location = Location(
        address=location_data['address'],
        full_address=location_data['full_address'],
        country=location_data['detail']['country'],
        lat=location_data['detail']['lat'],
        long=location_data['detail']['long'],
        region=location_data['detail']['region'],
        district=location_data['detail']['district'],
        city=location_data['detail']['city'],
        street=location_data['detail']['street'],
        house=location_data['detail']['house']
    )

    ad.location = location
    # Записываем объявление
    db.add(ad)
    db.commit()
    db.refresh(ad)
    ad_id = ad.id
    print('ad_id', ad_id)
    try:
        categories = form_data.get("categories")
        categories = json.loads(categories)
        # Записываем категории для объявления
        if categories:
            publish_categories(ad.id, categories, db)

    except Exception as e:
        logger.error(f"crud/ad. publish_adv. Ошибка, неправильно указаны категории: {key} => {str(e)}")
        print("Ошибка, неправильно указаны категории: ", str(e))
        return

    try:
        # Записываем доп.поля для объявления
        if fields:
            publish_fields(ad.id, fields, db)
    except Exception as e:
        # Обработка исключения при создании записей в модели AdFields
        print("Ошибка при создании записей в модели AdFields:", str(e))
        logger.error(f"crud/ad. publish_adv. Ошибка при создании записей в модели AdFields: {key} => {str(e)}")
        return

    try:
        # Устанавливаем статус-опубликовано и бэкграундом запускаем обработку и добавление фотографий
        ad_status = 3  # => status = publish
        background_tasks.add_task(save_images, images=photos, post_id=ad.id, status_id=ad_status, db=db)
    except Exception as e:
        # Обработка исключения при создании записей в модели AdFields
        print("Ошибка при добавлении изображений:", str(e))
        logger.error(f"crud/ad. publish_adv. Ошибка при добавлении изображений: {key} => {str(e)}")
        return

    try:
        if not ad.user.location:
            user_location = UserLocation(
                address=location_data['address'],
                full_address=location_data['full_address'],
                country=location_data['detail']['country'],
                lat=location_data['detail']['lat'],
                long=location_data['detail']['long'],
                region=location_data['detail']['region'],
                district=location_data['detail']['district'],
                city=location_data['detail']['city'],
                street=location_data['detail']['street'],
                house=location_data['detail']['house']
            )
            ad.user.location = user_location
            db.commit()
    except Exception as e:
        # Обработка исключения при создании записей в модели AdFields
        print("Ошибка при добавлении местоположения пользователя:", str(e))
        logger.error(f"crud/ad. publish_adv. Ошибка при добавлении местоположения пользователя: {key} => {str(e)}")
        return

    return ad_id


# Публикация доп.полей
def publish_fields(item_id, fields, db):
    for key, value in fields.items():
        str_value = str(value)
        if len(str_value) == 0:
            continue
        elif value or type(value) == bool:
            ad_field = AdFields(ad_id=item_id, key=key, value=str_value)
            db.add(ad_field)
    db.commit()
    return


# Редактирование объявления
def edit_adv(background_tasks, catalog_id, key, user_id, form_data, new_photos, out_type, db, old_photos):
    # key is Ad.id here
    ad = db.query(Ad).filter_by(id=key, user_id=user_id).first()
    errors = {}

    # Объявление не найдено
    if ad is None:
        return None

    # здесь получаем данные через if для каждого поля
    try:
        if "location" in form_data:
            location_data = json.loads(form_data.get("location"))

            invalid_location = validate_location(location_data)
            if invalid_location:  # Ошибки местоположения
                errors['location'] = invalid_location
            if errors:
                logger.error(f"crud/ad. edit_adv. Ошибка location: {key} => {errors}")
                raise HTTPException(status_code=400, detail=errors)

            # REQUIRED AND STRING + strip()
            ad.location.address = location_data["address"]
            ad.location.full_address = location_data["full_address"]
            ad.location.country = location_data['detail']['country']

            ad.location.lat = location_data['detail']['lat']
            ad.location.long = location_data['detail']['long']
            ad.location.region = location_data['detail']['region']
            ad.location.district = location_data['detail']['district']
            ad.location.city = location_data['detail']['city']
            ad.location.street = location_data['detail']['street']
            ad.location.house = location_data['detail']['house']

        title = None
        if "fields" in form_data:
            fields = json.loads(form_data.get("fields"))

            additional_fields_in_catalog = get_all_fields(ad.catalog_id, db)

            if additional_fields_in_catalog['additional_fields'] and fields:

                invalid_fields = validate_fields(additional_fields_in_catalog, fields, db)
                if invalid_fields['error'] or invalid_fields['aliases']:  # Ошибки доп.полей
                    errors['fields'] = invalid_fields

                if errors:
                    logger.error(f"crud/ad. edit_adv. Ошибка fields: {key} => {errors}")
                    raise HTTPException(status_code=400, detail=errors)

                # function to delete old fields, then publish - reUSE func
                invalid_delete_fields = delete_fields(ad.id, db)
                if invalid_delete_fields:  # Ошибки доп.полей
                    errors['fields'] = invalid_delete_fields

                if errors:
                    logger.error(f"crud/ad. edit_adv. Ошибка fields_2: {key} => {errors}")
                    raise HTTPException(status_code=400, detail=errors)

                # key_test = 'fb9ef210-10dc-4c4f-8261-448fb368faca'
                # key = ad id

                # создаем список нередактируемых полей
                not_editable_fields = check_if_editable(catalog_id, key, db)
                # и удаляем из списка fields все совпадения
                if not_editable_fields:
                    fields = {key: value for key, value in fields.items() if key not in not_editable_fields}

                title = get_dynamic_title(catalog_id, fields, db)

        if "title" in form_data and title is None:
            if not form_data["title"].strip():
                errors[FIELDS_LIST['title']] = "Обязательное поле"
            if len(form_data["title"].strip()) > 256:
                errors[FIELDS_LIST['title']] = "Длина заголовка не должна превышать 256 символов"
            ad.title = form_data["title"].strip()
        elif title is not None:
            ad.title = title
        # else:

        if "description" in form_data:
            if not form_data["description"].strip():
                errors[FIELDS_LIST['description']] = "Обязательное поле"
            if len(form_data["description"].strip()) > 4000:
                errors[FIELDS_LIST['description']] = "Длина описания не должна превышать 4000 символов"
            ad.description = form_data["description"].strip()

        if "price" in form_data:
            # REQUIRED AND INTEGER
            try:
                price_int = int(form_data["price"])
                if price_int <= 0:
                    errors[FIELDS_LIST['price']] = "Число не должно быть отрицательным"
            except:
                errors[FIELDS_LIST['price']] = "Неправильное значение"
            ad.price = form_data["price"]

        if "communication" in form_data:
            communication_data = json.loads(form_data["communication"])
            # REQUIRED AND BOOLEAN
            if type(communication_data["phone"]) != bool:
                invalid_form_data = {FIELDS_LIST['phone']: "Неправильное значение"}
                logger.error(f"crud/ad. edit_adv. Ошибка communication: {key} => {invalid_form_data}")
                raise HTTPException(status_code=400, detail=invalid_form_data)

            if type(communication_data["message"]) != bool:
                invalid_form_data = {FIELDS_LIST['message']: "Неправильное значение"}
                logger.error(f"crud/ad. edit_adv. Ошибка communication-message: {key} => {invalid_form_data}")
                raise HTTPException(status_code=400, detail=invalid_form_data)

            ad.contact_by_phone = communication_data["phone"]
            ad.contact_by_message = communication_data["message"]

            if not communication_data["phone"] and not communication_data["message"]:
                invalid_form_data = {FIELDS_LIST['message']: "Должен быть выбран хотя бы один способ связи"}
                logger.error(f"crud/ad. edit_adv. Ошибка communication-phone: {key} => {invalid_form_data}")
                raise HTTPException(status_code=400, detail=invalid_form_data)

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше
    except Exception as e:
        # Обработка исключения при загрузке и преобразовании данных местоположения и полей
        print("Ошибка при загрузке и преобразовании данных:", str(e))
        errors['form_data'] = "Ошибка при загрузке и преобразовании данных"
        logger.error(f"crud/ad. edit_adv. Ошибка при загрузке и преобразовании данных: {key} => {str(e)}")
        raise HTTPException(status_code=400, detail=errors)
    if errors:
        logger.error(f"crud/ad. edit_adv. Ошибки при редактировании объявления: {key} => {errors}")
        raise HTTPException(status_code=400, detail=errors)

    try:
        status_id = 1
        old_status = change_post_status(post_id=key, status_id=status_id, db=db)

        if "fields" in form_data:
            fields = json.loads(form_data.get("fields"))
            publish_fields(ad.id, fields, db)

        ad.updated_at = datetime.now()
        db.commit()

        status_id = old_status
        background_tasks.add_task(save_images, images=new_photos, post_id=ad.id, status_id=status_id, db=db, old_photos=old_photos)
    except Exception as e:
        # Обработка исключения при создании записей в модели AdFields
        print("Ошибка при добавлении изображений:", str(e))
        errors['form_data'] = "Ошибка при изменении статуса, добавлении новых изображений или публикации доп. полей"
        logger.error(f"crud/ad. delete_fields. Ошибка: {key} => {str(e)}")
        raise HTTPException(status_code=400, detail=errors)

    # out_type = 'card'
    # out_type = 'minicard'

    if out_type == 'minicard':
        photos = ad.photos[0].id if ad.photos else ''
        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict(),
            photos=photos,
            favorite=False,
            status=ad.status.status,
            created_at=str(ad.created_at)
        )
    else:
        photos = [photo.id for photo in ad.photos] if ad.photos else []
        communication = {
            method: getattr(ad, f"contact_by_{method}")
            for method in ["phone", "message"]
        }

        if user_id:
            favorite = user_id in [user.id for user in ad.favorited_by]
        else:
            favorite = False

        fields = get_fields_to_adv(ad.catalog_id, ad.fields, db)
        owner = get_owner_lite_to_adv(ad.user_id, db)
        owner_out = set_owner_out_lite_model_to_adv(owner)
        ad_out = set_ad_out_model_to_adv(ad, communication, fields, photos, owner_out, favorite)

    return ad_out


# Удаление доп.полей
def delete_fields(item_id, db):
    try:
        db.query(AdFields).filter_by(ad_id=item_id).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print("Ошибка обновления полей:", str(e))
        logger.error(f"crud/ad. delete_fields. Ошибка удаления доп. полей: {item_id} => {str(e)}")
        return {"Ошибка обновления полей"}
    return None


# Публикация категорий
def publish_categories(ad_id, categories, db):
    for value in categories:
        adv_categories = AdvCategories(adv_id=ad_id, category_id=value)
        db.add(adv_categories)
    db.commit()
    return


# Изменение статуса своего объявления для текущего пользователя
def change_status_adv(key, advs, status, db):
    ad_ids = [ad.id for ad in advs]

    if key not in ad_ids:
        logger.error(f"crud/ad. change_status_adv. Объявление не найдено: {key}")
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    try:
        # Изменение статуса объявления
        change_post_status(db, key, status)
    except:
        logger.error(f"crud/ad. change_status_adv. Ошибка при изменении статуса: {key} => {status}")
        raise HTTPException(status_code=400, detail="Ошибка при изменении статуса")

    return {"status": "Changed"}


# Проверка - редактируемые поля или нет - edit=True/False
def check_if_editable(catalog_id, item_id, db):
    catalog_fields = get_all_fields(catalog_id, db)
    current_fields = db.query(AdFields).filter_by(ad_id=item_id).all()
    not_editable_list = []

    for current_field in current_fields:
        catalog_items = [catalog_item for catalog_item in catalog_fields['additional_fields'] if
                         catalog_item.get('alias') == current_field.key]
        editable_field = catalog_items[0]['data']['edit']

        if not editable_field:
            not_editable_list.append(current_field.key)

    return not_editable_list


# Функция запроса на получения объявлений с учётом фильтров, сортировки и поиска, а также формирования выдачи
def get_paginated_advs(query_type, category, sort, page, limit, status, db, current_user, filters, price_from, price_to,
                       location, search, radius, auth_user_id=None):
    offset = (page - 1) * limit  # Получаем значение смещения для пагинации

    ads, total = get_query_by_type(query_type, sort, category, status, current_user, db, filters, offset, limit,
                                   price_from, price_to, location, search, radius)

    ad_list = []
    for ad in ads:
        photos = ad.photos[0].id if ad.photos else ''
        if auth_user_id is not None:
            favorite = auth_user_id in [user.id for user in ad.favorited_by]
            # print(f'auth_user_id {auth_user_id}: ad_id: {ad.id} - {favorite}')
        else:
            # favorite = current_user in [user.id for user in ad.favorited_by]
            favorite = False

        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict() if ad.location else {},
            photos=photos,
            favorite=favorite,
            status=ad.status.status,
            created_at=str(ad.created_at)
        )
        ad_list.append(ad_out)

    return PaginatedItems(total=total, items=ad_list)


# Функция получения списка объявлений с учётом фильтров, сортировки и поиска
def get_query_by_type(query_type, sort, category, status, user_id, db, filters, offset, limit, price_from,
                      price_to, location, search, radius):
    # query_type = 'all_no_user_no_category'
    # Получаем объявления со статусом=опубликовано с полученной сортировкой

    if status == 2:
        status_values = [status, 5]
        query = db.query(Ad).filter(or_(Ad.status_id == val for val in status_values))
    elif status == 3:
        status_values = [status, 1] if query_type == 'card' else [status]
        query = db.query(Ad).filter(or_(Ad.status_id == val for val in status_values))
    else:
        query = db.query(Ad).filter(Ad.status_id == status)

    # Основываясь на типе запроса применяем фильтры
    if query_type == 'card':
        query = query.filter(Ad.user_id == user_id)

    elif query_type == 'all_user_category':
        query = (
            query
            .join(Ad.categories)
            .filter(Ad.user_id != user_id, AdvCategories.category_id == category)
        )

    elif query_type == 'all_user_no_category':
        query = query.filter(Ad.user_id != user_id)

    elif query_type == 'all_no_user_category':
        query = (
            query
            .join(Ad.categories)
            .filter(AdvCategories.category_id == category)
        )
    sort_column = (  # Сортируем объявления по значению sort
        Ad.created_at.asc() if sort == 'date_asc' else
        Ad.created_at.desc() if sort == 'date_desc' else
        Ad.price.asc() if sort == 'price_asc' else
        Ad.price.desc() if sort == 'price_desc' else
        Ad.created_at.desc()
    )


    # Если получены фильтры местроположения, то применяем их
    if location and radius is None:
        region = location.get('region', None)
        city = location.get('city', None)
        district = location.get('district', None)

        # Filter based on location fields
        location_clauses = []

        if district:
            if isinstance(district, list):
                location_clauses.append(Location.district.in_(district))
            else:
                location_clauses.append(Location.district == district)

        if city:
            location_clauses.append(Location.city == city)

        if region:
            location_clauses.append(Location.region == region)

        if location_clauses:
            # Используем подзапрос для выбора объявлений с заданным местоположением
            subquery = (
                db.query(Location.ad_id)
                .filter(and_(*location_clauses))
                .subquery()
            )

            # Присоединяем подзапрос к основному запросу объявлений
            query = query.join(subquery, Ad.id == subquery.c.ad_id)

    # Если получены фильтры доп.полей, то применяем их
    if filters:
        list_of_ranges = LIST_OF_RANGES

        # Ищем словарь, например с ключом "2ef8bb1c-e994-4cf0-bbac-e5c58175502e"
        try:
            filtered_dict = next(item for item in list_of_ranges if category in item)
            # Получаем значение для ключа "2ef8bb1c-e994-4cf0-bbac-e5c58175502e"
            exception_filters_list = filtered_dict[category]
        except StopIteration:
            exception_filters_list = []

        filter_clauses = []
        for key, value in filters.items():

            # == EXCEPTION_FILTERS ==
            # объект с ключом year_of_issue в котором есть поля ключ(from):значение(строка) и ключ(to):значение(строка)
            # выборка тех записей в которых значение key(year_of_issue) >= from и <= to
            if key in exception_filters_list:
                # Обработка фильтрации для year_of_issue с полями from и to
                if isinstance(value, dict):
                    value_from = value.get('from', None)
                    value_to = value.get('to', None)

                    if value_from == 'null':
                        value_from = None

                    if value_to == 'null':
                        value_to = None

                    if value_from and value_to and value_from != '' and value_to != '':
                        filter_clauses.append(
                            and_(
                                AdFields.key == key,
                                cast(AdFields.value, Integer).between(int(value_from), int(value_to))
                            )
                        )
                    elif value_from and value_from != '':
                        filter_clauses.append(
                            and_(
                                AdFields.key == key,
                                cast(AdFields.value, Integer) >= int(value_from)
                            )
                        )
                    elif value_to and value_to != '':
                        filter_clauses.append(
                            and_(
                                AdFields.key == key,
                                cast(AdFields.value, Integer) <= int(value_to)
                            )
                        )

            # == MAIN_FILTERS ==
            elif isinstance(value, list):
                # список, ключ - значения(строки) - одно из значений совпадает
                value_filters = [AdFields.value.ilike(f'%{item}%') for item in value]
                filter_clauses.append(and_(AdFields.key == key, or_(*value_filters)))
            else:
                # обычные поля, ключ - значение(строка) - строго только это значение
                filter_clauses.append(and_(AdFields.key == key, AdFields.value == value))

        subquery = (
            db.query(AdFields.ad_id)
            .filter(or_(*filter_clauses))
            .group_by(AdFields.ad_id)
            .having(func.count(distinct(AdFields.key)) == len(filters))
            .as_scalar()
        )
        query = query.filter(Ad.id.in_(subquery))

    # Если получены фильтры цены, то применяем их
    if price_from is not None:
        query = query.filter(Ad.price >= int(price_from))

    if price_to is not None:
        query = query.filter(Ad.price <= int(price_to))

    # Если получено поле поиска, то применяем поиск
    if search:
        search = search.strip()  # Remove leading/trailing whitespaces
        search_clause = or_(
            Ad.title.ilike(f'%{search}%'),
            Ad.description.ilike(f'%{search}%')
        )
        query = query.filter(search_clause)

    # Если получены фильтры местоположения и радиус, то применяем их
    if location and radius:
        latitude = location.get('lat', None)
        longitude = location.get('long', None)
        if sort:
            query = query.order_by(sort_column)
        if latitude is not None and longitude is not None:
            lat1, lon1 = radians(float(latitude)), radians(float(longitude))

            # Alias for the Location table
            loc_alias = aliased(Location)

            # Add filter for distance comparison using the join
            query = query.join(loc_alias, Ad.id == loc_alias.ad_id)
            query = query.filter(
                func.acos(
                    func.sin(func.radians(cast(loc_alias.lat, Float))) * func.sin(lat1)
                    + func.cos(func.radians(cast(loc_alias.lat, Float))) * func.cos(lat1)
                    * func.cos(func.radians(cast(loc_alias.long, Float)) - lon1)
                )
                * 6371  # Earth's radius in kilometers
                <= radius
            )

            # Вычисляем расстояние от заданной точки до местоположения объявления
            distance_expression = (
                    func.acos(
                        func.sin(func.radians(cast(loc_alias.lat, Float))) * func.sin(lat1)
                        + func.cos(func.radians(cast(loc_alias.lat, Float))) * func.cos(lat1)
                        * func.cos(func.radians(cast(loc_alias.long, Float)) - lon1)
                    )
                    * 6371 * 1000  # Convert Earth's radius to meters
            )
            # Добавляем сортировку по расстоянию (возрастание)
            query = query.order_by(distance_expression.asc())
    else:
        query = query.order_by(sort_column)

    # Получаем общее кол-во полученных записей и применяем пагинацию
    total = query.count()
    ads = query.offset(offset).limit(limit).all()
    return ads, total


def get_adv_data(key, db):
    ad = db.query(Ad).get(key)
    if not ad:
        logger.error(f"crud/ad- get_adv_data. Объявление не найдено: {key}")
    return ad


def get_adv_out(ad, user_id, db):
    communication = {
        "phone": ad.contact_by_phone,
        "message": ad.contact_by_message
    }

    fields = get_fields_to_adv(ad.catalog_id, ad.fields, db)

    if ad.photos:
        photos = [photo.id for photo in ad.photos]
    else:
        photos = []

    if user_id:
        favorite = user_id in [user.id for user in ad.favorited_by]
    else:
        favorite = False

    # ad.views += 1
    # db.commit()

    owner, user_ads, user_ads_count  = get_owner_to_adv(ad.user_id, ad.id, db)
    adv_list = set_owner_advlist_to_adv(user_ads, ad.status.status, user_id)
    owner_out = set_owner_out_model_to_adv(owner, user_ads_count, adv_list, ad.contact_by_phone)
    ad_out = set_ad_out_model_to_adv(ad, communication, fields, photos, owner_out, favorite)

    return ad_out


def get_fields_to_adv(catalog_id, adv_fields, db):
    fields = {}

    catalogs = db.query(Catalog).filter(Catalog.id == catalog_id).outerjoin(AdditionalFields).filter(
        or_(AdditionalFields.parent_id != None, AdditionalFields.parent_id == None)).all()

    additional_fields = catalogs[0].additional_fields
    if adv_fields:
        for field in adv_fields:
            matching_field = next((item for item in additional_fields if item.alias == field.key), None)
            if matching_field:
                try:
                    field_value_list = ast.literal_eval(field.value)
                    fields[matching_field.title] = field_value_list
                except (SyntaxError, ValueError):
                    value = field.value.lower()
                    fields[
                        matching_field.title] = True if value == "true" else False if value == "false" else field.value
    return fields


def get_owner_to_adv(user_id, key, db):
    owner = db.query(User).get(user_id)
    check_user_online(owner, db)

    user_ads = db.query(Ad).order_by(Ad.created_at.desc()).filter(Ad.user_id == owner.id, Ad.id != key,
                                                                  Ad.status_id == 3).limit(2).all()
    user_ads_count = db.query(func.count(Ad.id)).filter(Ad.user_id == owner.id, Ad.status_id == 3).scalar()

    return owner, user_ads, user_ads_count


def get_owner_lite_to_adv(user_id, db):
    owner = db.query(User).get(user_id)
    check_user_online(owner, db)
    return owner


def set_owner_advlist_to_adv(user_ads, ad_status, user_id):
    adv_list = []
    for user_ad in user_ads:
        if user_ad.photos:
            user_photos = user_ad.photos[0].id
        else:
            user_photos = ''

        if user_id:
            favorite = user_id in [user.id for user in user_ad.favorited_by]
        else:
            favorite = False

        # Создание объекта AdAdvModel для каждого объявления пользователя
        adv = ItemsOutModel(
            id=user_ad.id,
            title=user_ad.title,
            description=user_ad.description,
            price=user_ad.price,
            location=user_ad.location.to_dict(),
            photos=user_photos,
            favorite=favorite,
            status=ad_status,
            created_at=str(user_ad.created_at)
        )
        adv_list.append(adv)
    return adv_list


def set_owner_out_model_to_adv(owner, user_ads_count, adv_list, contact_by_phone):
    photo_id = None
    if owner.photo:
        photo_id = str(owner.photo.id)
    owner_out = OwnerOutModel(
        id=str(owner.id),
        name=str(owner.name),
        photo=photo_id,
        rating=owner.rating,
        feedback_count=owner.feedback_count,
        online=owner.online,
        online_at=owner.online_at,
        is_active=owner.is_active,
        phone=owner.phone if contact_by_phone else None,
        adv_count=user_ads_count
    )
    owner_out.adv = adv_list

    return owner_out


def set_owner_out_lite_model_to_adv(owner):
    photo_id = None
    if owner.photo:
        photo_id = str(owner.photo.id)
    owner_out = OwnerOutModel(
        id=str(owner.id),
        name=str(owner.name),
        photo=photo_id,
        rating=owner.rating,
        feedback_count=owner.feedback_count,
        online=owner.online,
        online_at=owner.online_at,
        is_active=owner.is_active,
        phone=owner.phone,
        adv_count=None,
        adv=None
    )
    return owner_out


def set_ad_out_model_to_adv(ad, communication, fields, photos, owner_out, favorite):
    ad_out = AdOutModel(
        id=ad.id,
        title=ad.title,
        description=ad.description,
        price=ad.price,
        location=ad.location.to_dict() if ad.location else {},
        communication=communication,
        fields=fields,
        photos=photos,
        favorite=favorite,
        created_at=str(ad.created_at),
        views=ad.views,
        status=ad.status.status,
        owner=owner_out
    )
    return ad_out


async def inc_adv_unique_views(current_user_id, device_id, adv, db):
    if current_user_id:
        adv_views_auth = db.query(AdvViews).filter(AdvViews.device_id == device_id,
                                                     AdvViews.adv_viewed_id == adv.id,
                                                     AdvViews.user_id == current_user_id).first()

        # Если нет записей с авторизацией, проверям есть ли записи без авторизации для текущего устройства
        if not adv_views_auth:
            adv_views_no_auth = db.query(AdvViews).filter(AdvViews.device_id == device_id,
                                                            AdvViews.adv_viewed_id == adv.id,
                                                            AdvViews.user_id == None).first()

            # Если нет записей БЕЗ авторизации, то создаем новую и увеличиваем просмотры
            if not adv_views_no_auth:
                # CREATE NEW views record without auth => then =>
                new_adv_view = AdvViews(id=uuid.uuid4(),
                                          user_id=current_user_id,
                                          adv_viewed_id=adv.id,
                                          device_id=device_id,
                                          created_at=get_current_time2())
                db.add(new_adv_view)
                adv.views += 1
                db.commit()



            # Если существует запись БЕЗ авторизации, добавляем в эту запись авторизацию
            else:
                adv_views_no_auth.user_id = current_user_id
                db.commit()

        # Если запись с авторизацией уже есть, то пропускаем
        else:
            pass

    # Если запрос без авторизации
    else:
        # Проверяем существуют ли записи без учета авторизации для текущего устройства
        adv_views_no_auth = db.query(AdvViews).filter(AdvViews.device_id == device_id,
                                                        AdvViews.adv_viewed_id == adv.id).first()
        # Если нет записей, то создаем новую и увеличиваем просмотры
        if not adv_views_no_auth:
            # CREATE NEW views record without auth => then =>
            new_adv_view = AdvViews(id=uuid.uuid4(),
                                      adv_viewed_id=adv.id,
                                      device_id=device_id,
                                      created_at=get_current_time2())
            db.add(new_adv_view)
            adv.views += 1
            db.commit()

        # Если нашли хоть одну запись для текущего устройства, то пропускаем
        else:
            pass
