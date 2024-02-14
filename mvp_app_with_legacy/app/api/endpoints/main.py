import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.sql.expression import or_

from app.crud.main import get_app_version, get_documents_by_type, get_advs_count, get_active_users_count
from app.db.db_models import Ad, MainCatalogTitle
from app.logger import setup_logger
from app.schemas.main import AppVersionData, AutocompleteData, InfoDocumentsOut
from app.utils.dependencies import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/main", tags=["Main data"])
logger = setup_logger(__name__)


# Получаем версию приложения
@router.get('/version', summary="Get App version", status_code=200, response_model=AppVersionData)
async def get_version(db: Session = Depends(get_db)):
    """
    Получение версии приложения.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - version: строковое значение версии.
    """

    # Вызываем функцию получения версии приложения
    version = await get_app_version(db)
    # Если не получена запись - выводим ошибку
    if not version:
        logger.error(f"api/endpoints/main- get_version. Версия приложения не найдена")
        raise HTTPException(status_code=404, detail="Version not found")
    return {"version": version}


# Автокомплит для строки поиска
@router.get("/autocomplete", summary="Get autocomplete for search", status_code=200, response_model=AutocompleteData)
async def autocomplete_search(
        search: str = Query(..., min_length=2),
        db: Session = Depends(get_db)
):
    """
    Получение Автокомплита для поиска.

    Параметры:
    - search: Текст поиска (от 2-х символов).
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - categories: список объектов => id=идентификатор категории, filter=Наименование категории. до 3-х значений.
    - autocomplete: список строк => значения из заголовков и описания объявлений. до 7 значений. (отключено, пустое значение)
    """

    search = search.strip().lower()

    # search_clause = or_(
    #     Ad.title.ilike(f'%{search}%'),
    #     Ad.description.ilike(f'%{search}%')
    # )
    # query = db.query(Ad).filter(search_clause).limit(7)
    #
    # results = query.all()
    #
    # autocomplete_set = set()  # Множество для хранения уникальных результатов
    # for result in results:
    #     title_lower = result.title.lower()
    #     description_lower = result.description.lower()
    #
    #     # Поиск окончания слова и следующего слова с использованием регулярных выражений
    #     pattern = re.compile(rf'\b({re.escape(search)}\S*)\s*(\S+)?\b')
    #     title_matches = pattern.findall(title_lower)
    #     description_matches = pattern.findall(description_lower)
    #
    #     for match in title_matches:
    #         if match[1]:
    #             autocomplete_set.add(' '.join(match))
    #         else:
    #             autocomplete_set.add(match[0])
    #
    #     for match in description_matches:
    #         if match[1]:
    #             autocomplete_set.add(' '.join(match))
    #         else:
    #             autocomplete_set.add(match[0])
    #
    # autocomplete_list = list(autocomplete_set)

    # Поиск в модели MainCatalogTitle
    # main_catalog_title_query = db.query(MainCatalogTitle).filter(
    #     MainCatalogTitle.filter.ilike(f'%{search}%')
    # )
    #
    # main_catalog_title_results = main_catalog_title_query.limit(3)

    main_catalog_title_results = (
        db.query(MainCatalogTitle)
        .filter(MainCatalogTitle.filter.ilike(f'%{search}%'))
        .limit(3)
        .all()
    )

    categories = []
    for result in main_catalog_title_results:
        category = {
            "id": result.parent_id,
            "filter": result.filter
        }
        categories.append(category)

    autocomplete_list = []
    # Объединение результатов
    response = {
        "categories": categories,
        "autocomplete": autocomplete_list
    }

    return response


@router.get('/terms', summary="Get Terms of Use", status_code=200)
async def get_terms(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """
    doc_type = 'terms'
    # Вызываем функцию получения версии приложения
    terms = await get_documents_by_type(doc_type, db)

    # Если не получена запись - выводим ошибку
    if not terms:
        logger.error(f"api/endpoints/main- get_terms. Условия пользования не найдены")
        raise HTTPException(status_code=404, detail="Terms not found")
    return terms


@router.get('/offer', summary="Get Offer to Use Services", status_code=200)
async def get_offer(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """

    doc_type = 'offer'
    # Вызываем функцию получения версии приложения
    offer = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not offer:
        logger.error(f"api/endpoints/main- get_offer. Оферта не найдена")
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.get('/license', summary="Get License", status_code=200, response_model=InfoDocumentsOut)
async def get_license(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """

    doc_type = 'license'
    # Вызываем функцию получения версии приложения
    kvik_license = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not kvik_license:
        logger.error(f"api/endpoints/main- get_license. Лицензионное соглашение не найдено")
        raise HTTPException(status_code=404, detail="License not found")
    return kvik_license


@router.get('/seller_codex', summary="Get Seller Codex", status_code=200)
async def get_seller_codex(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """

    doc_type = 'seller_codex'
    # Вызываем функцию получения версии приложения
    seller_codex = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not seller_codex:
        logger.error(f"api/endpoints/main- get_seller_codex. Кодекс правил не найден")
        raise HTTPException(status_code=404, detail="Seller codex not found")
    return seller_codex


@router.get('/privacy', summary="Get Privacy Policy", status_code=200)
async def get_privacy(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """

    doc_type = 'privacy'
    # Вызываем функцию получения версии приложения
    privacy = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not privacy:
        logger.error(f"api/endpoints/main- get_privacy. Политика конфиденциальности не найдена")
        raise HTTPException(status_code=404, detail="Privacy Policy not found")
    return privacy


@router.get('/agreement', summary="Get User Agreement", status_code=200)
async def get_agreement(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """

    doc_type = 'agreement'
    # Вызываем функцию получения версии приложения
    agreement = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not agreement:
        logger.error(f"api/endpoints/main- get_agreement. Пользовательское соглашение не найдено")
        raise HTTPException(status_code=404, detail="Agreement not found")
    return agreement


@router.get('/rules', summary="Get CLEEX Rules", status_code=200)
async def get_rules(db: Session = Depends(get_db)):
    """
    Получение Условий пользования.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Условий пользования.
    """

    doc_type = 'rules'
    # Вызываем функцию получения версии приложения
    rules = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not rules:
        logger.error(f"api/endpoints/main- get_rules. Правила Кликса не найдены")
        raise HTTPException(status_code=404, detail="Rules not found")
    return rules


@router.get('/user_policy', summary="Get CLEEX User Policy", status_code=200)
async def get_user_policy(db: Session = Depends(get_db)):
    """
    Политика о данных пользователей CLEEX

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - terms: Текст Политики о данных пользователей CLEEX
    """

    doc_type = 'user_policy'
    # Вызываем функцию получения версии приложения
    rules = await get_documents_by_type(doc_type, db)
    # Если не получена запись - выводим ошибку
    if not rules:
        logger.error(f"api/endpoints/main- get_rules.Политика о данных пользователей не найдена")
        raise HTTPException(status_code=404, detail="User's policy not found")
    return rules


@router.get('/stats', summary="Get App Stats", status_code=200)
async def get_stats(db: Session = Depends(get_db)):
    """
    Получить статистику CLEEX

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - stats: Статистика CLEEX
    """

    # Вызываем функцию получения версии приложения
    advs_count = await get_advs_count(db)
    users_count = await get_active_users_count(db)
    return {
        "advs_count": advs_count,
        "users_count": users_count
    }