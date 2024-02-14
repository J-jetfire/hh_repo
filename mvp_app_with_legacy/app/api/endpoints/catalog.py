import json
from typing import List, Dict
from uuid import UUID

from fastapi_cache.decorator import cache
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.schemas.catalog import CatalogSchema, CatalogSchemaAdditionalFields
from app.utils.dependencies import get_db
from app.crud.catalog import get_catalog, get_all_fields
from app.utils.additional_fields import validate_fields
from app.utils.redis import custom_key_builder

router = APIRouter(prefix="/catalog", tags=["Catalog"])


# Получение каталога с категориями
@router.get("", summary="Get catalog", status_code=200, response_model=List[CatalogSchema])
@cache(namespace="catalog", expire=3600, key_builder=custom_key_builder)
async def get_catalog_data(db: Session = Depends(get_db)):
    """
    Получение каталога

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список всех объектов каталога
    """
    catalog = get_catalog(db) # получаем каталог
    return catalog


# Получение всех доп.полей
@router.get("/fields", summary="Get all additional fields", response_model=List[CatalogSchemaAdditionalFields])
@cache(namespace="fields", expire=3600, key_builder=custom_key_builder)
async def get_additional_fields(db: Session = Depends(get_db)):
    """
    Получение всех доп.полей каталога

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список всех объектов каталога с доп.полями
    """
    key = None
    fields = get_all_fields(key, db) # получаем весь каталог с доп.полями
    return fields


# Получение доп.поля по идентификатору каталога
@router.get("/fields/{key}", summary="Get additional fields by UUID", response_model=CatalogSchemaAdditionalFields)
@cache(namespace="field_by_key", expire=3600, key_builder=custom_key_builder)
async def get_additional_fields_by_key(key: UUID, db: Session = Depends(get_db)):
    """
    Получение доп.полей по идентификатору каталога

    Параметры:
    - key: Идентификатор каталога.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Объект каталога с доп.полями
    """
    field = get_all_fields(key, db) # получаем один раздел каталога с его доп.полями
    return field


@router.post("/validate_fields/{key}", summary="Validate additional fields", status_code=200)
async def validate_addit_fields(
        data: Dict,
        key: UUID,
        db: Session = Depends(get_db)):
    """
    Валидация доп.полей перед подачей объявления

    Параметры:
    - data: Тело запроса.
    - key: Идентификатор каталога.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Список ошибок, если имеются, или пустой объект {'error': "", 'aliases': {}}
    """
    field = get_all_fields(key, db) # Получаем доп.поля по идентификатору каталога
    invalid_data = validate_fields(field, data, db) # Валидируем поля из запроса
    content = json.dumps(invalid_data)

    status_code = 400 if invalid_data['error'] or invalid_data['aliases'] else 200
    # Если валидация пройдена возвращаем пустые значения, иначе список ошибок
    return Response(content=content, status_code=status_code, media_type="application/json")
