import json
from typing import List

from fastapi import HTTPException, UploadFile

from app.db.db_models import Catalog
from app.logger import setup_logger
from app.schemas.ad import LocationOutModel

from app.crud.catalog import get_all_fields
from app.utils.additional_fields import validate_fields
from app.db.list_constants import FIELDS_LIST, ALLOWED_FORMATS
logger = setup_logger(__name__)

def get_dynamic_title(key, fields, db):
    # key = для этого ключа ищем в элементе каталога поле dynamic_title
    # Если оно не пустое, то достаем значения.
    # Проходим по этим значениям и ищем совпадения в списке ключей присланных данных доп.полей
    # Если из ключ dynamic_title совпадает с ключом строки,
    # то в отдельную строку добавляем значение присланной строки
    # Если пустое заполняем обычно title = form_data.get("title")
    title = ""
    try:
        dynamic_title_field = db.query(Catalog).filter_by(id=key).first().dynamic_title
        try:
            for dynamic_title in dynamic_title_field:
                if dynamic_title.title in fields:
                    title += fields[dynamic_title.title] + ' '

        except Exception as e:
            logger.error(f"utils/ad. get_dynamic_title. Ошибка 1: {str(e)}")
            # print("Ошибка при генерации dynamic title:", str(e))
            return None
    except Exception as e:
        logger.error(f"utils/ad. get_dynamic_title. Ошибка 2: {str(e)}")
        # print("Ошибка при получении данных для dynamic title:", str(e))
        return None
    if title:
        return title.rstrip()
    return None


def validate_ad(key, form_data, db):
    try:
        field = get_all_fields(key, db)
    except:
        invalid_fields = "По этому ID не найдены доп.поля"
        logger.error(f"utils/ad. validate_ad. Ошибка 1: {invalid_fields}")
        raise HTTPException(status_code=400, detail=invalid_fields)

    try:
        description = form_data.get("description")
        price = form_data.get("price")

        communication = form_data.get("communication")
        communication = json.loads(communication)

        additional_fields = form_data.get("fields")
        additional_fields = json.loads(additional_fields)

        location_data = form_data.get("location")
        location_data = json.loads(location_data)

        categories = form_data.get("categories")
        categories = json.loads(categories)

        dynamic_title = get_dynamic_title(key, additional_fields, db)
        title = dynamic_title if dynamic_title else form_data.get("title")
        # print(title)

        contact_by_phone = communication['phone']
        contact_by_message = communication['message']

        if type(contact_by_phone) != bool:
            invalid_form_data = {FIELDS_LIST['phone']: "Неправильное значение"}
            logger.error(f"utils/ad. validate_ad. Ошибка 2: {invalid_form_data}")
            raise HTTPException(status_code=400, detail=invalid_form_data)

        if type(contact_by_message) != bool:
            invalid_form_data = {FIELDS_LIST['message']: "Неправильное значение"}
            logger.error(f"utils/ad. validate_ad. Ошибка 3: {invalid_form_data}")
            raise HTTPException(status_code=400, detail=invalid_form_data)

        if (not contact_by_phone) and (not contact_by_message):
            invalid_form_data = {FIELDS_LIST['message']: "Должен быть выбран хотя бы один вид связи"}
            logger.error(f"utils/ad. validate_ad. Ошибка 4: {invalid_form_data}")
            raise HTTPException(status_code=400, detail=invalid_form_data)

        try:
            invalid_categories = validate_categories(key, categories, db)

            invalid_form_data = validate_form_data(title, description, price)
            if field['additional_fields'] or additional_fields:
                invalid_fields = validate_fields(field, additional_fields, db)
            else:
                invalid_fields = {'error': "", 'aliases': {}}
            invalid_location = validate_location(location_data)
        except:
            invalid_form_data = {"form_data": "Неправильный формат данных"}
            logger.error(f"utils/ad. validate_ad. Ошибка 5: {invalid_form_data}")
            raise HTTPException(status_code=400, detail=invalid_form_data)
    except:
        invalid_form_data = {"form_data": "Неправильный формат данных"}
        logger.error(f"utils/ad. validate_ad. Ошибка 6: {invalid_form_data}")
        raise HTTPException(status_code=400, detail=invalid_form_data)

    errors = {}  # Все ошибки

    if invalid_categories:  # Ошибки в категориях
        errors['categories'] = invalid_categories
    if invalid_form_data:  # Ошибки в форме из запроса
        errors['form_data'] = invalid_form_data
    if invalid_fields['error'] or invalid_fields['aliases']:  # Ошибки доп.полей
        errors['fields'] = invalid_fields
    if invalid_location:  # Ошибки местоположения
        errors['location'] = invalid_location

    if errors:
        logger.error(f"utils/ad. validate_ad. Ошибки при валидации объявления: {errors}")
        raise HTTPException(status_code=400, detail=errors)


def validate_location(location_data: dict):
    try:
        errors = {}

        if 'address' not in location_data or not location_data['address'].strip():
            errors[FIELDS_LIST['address']] = "Обязательное поле"

        if 'full_address' not in location_data or not location_data['full_address'].strip():
            errors[FIELDS_LIST['full_address']] = "Обязательное поле"

        if 'detail' not in location_data:
            errors[FIELDS_LIST['country']] = "Обязательное поле"
        else:
            if 'country' not in location_data['detail'] or not location_data['detail']['country'].strip():
                errors[FIELDS_LIST['country']] = "Обязательное поле"

        if not any(errors.values()):
            try:
                location_model = LocationOutModel(**location_data)
            except ValueError as e:
                logger.error(f"utils/ad. validate_location. Неправильный формат данных 1: {str(e)}")
                return {FIELDS_LIST['location']: "Неправильный формат данных"}
            return {}

        return errors

    except ValueError as e:
        logger.error(f"utils/ad. validate_location. Неправильный формат данных 2: {str(e)}")
        return {FIELDS_LIST['location']: "Неправильный формат данных"}


def validate_form_data(title, description, price):
    try:
        errors = {}
        if not title.strip():
            errors[FIELDS_LIST['title']] = "Обязательное поле"
        if not description.strip():
            errors[FIELDS_LIST['description']] = "Обязательное поле"
        if len(title.strip()) > 256:
            errors[FIELDS_LIST['title']] = "Длина заголовка не должна превышать 256 символов"
        if len(description.strip()) > 4000:
            errors[FIELDS_LIST['description']] = "Длина описания не должна превышать 4000 символов"
        if price:

            try:
                price_int = int(price)

                if price_int <= 0:
                    errors[FIELDS_LIST['price']] = "Число не должно быть отрицательным"
            except:
                errors[FIELDS_LIST['price']] = "Неправильное значение"

        else:
            errors[FIELDS_LIST['price']] = "Обязательное поле"

        if not any(errors.values()):
            return {}
        else:
            return errors

    except ValueError as e:
        logger.error(f"utils/ad. validate_form_data. Неправильный формат данных: {str(e)}")
        return {"form_data": "Неправильный формат данных"}


def validate_photos(photos: List[UploadFile]):
    for photo in photos:
        # Проверка, содержит ли поле photos файлы
        if not photo.content_type.startswith('image/'):
            detail_mess = {FIELDS_LIST['photos']: "Недопустимый формат файла. Разрешены только изображения."}
            logger.error(f"utils/ad. validate_photos. Ошибки валидации фотографий: {detail_mess}")
            raise HTTPException(status_code=400, detail=detail_mess)
        # Получение расширения файла
        file_extension = photo.filename.split('.')[-1].lower()
        # Проверка формата файла
        if file_extension not in ALLOWED_FORMATS:
            detail_mess = {FIELDS_LIST['photos']: "Недопустимый формат фото. Разрешены только форматы JPG, JPEG, PNG, HEIC, HEIF, и WEBP."}
            logger.error(f"utils/ad. validate_photos. Ошибки валидации фотографий: {detail_mess}")
            raise HTTPException(status_code=400,
                                detail=detail_mess)


def validate_categories(key, categories, db):
    # key должен быть в списке categories
    if str(key) not in categories:
        errors = "Ошибка категорий"
        logger.error(f"utils/ad. validate_categories. Ошибка 1: {errors}")
        return errors

    catalog_id = key
    catalog_list = [str(key)] # list of strings

    while catalog_id:
        catalog_id = db.query(Catalog.parent_id).filter(Catalog.id==catalog_id).first()[0]

        if catalog_id is not None:
            catalog_list.append(str(catalog_id))
        else:
            catalog_id = None

    for category in categories:
        if category not in catalog_list:
            errors = "Ошибка категорий"
            logger.error(f"utils/ad. validate_categories. Ошибка 2: {errors}")
            return errors

    return {}
