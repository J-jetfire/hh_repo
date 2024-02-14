from sqlalchemy.orm import Session, joinedload
from app.db.db_models import AppVersion, InfoDocuments, Ad, User
from app.logger import setup_logger
from app.schemas.main import InfoDocumentsRulesOut, InfoDocumentsOut
logger = setup_logger(__name__)

# Функция получения версии приложения из БД
async def get_app_version(db: Session):
    """
    Получение версии приложения.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - version: строковое значение версии.
    """
    # В БД содержится одна запись - получаем её
    version = db.query(AppVersion.version).first()
    if not version:
        logger.error(f"crud/main- get_app_version. Не удалось получить версию приложения")
        return False
    return version[0]


async def get_documents_by_type(doc_type, db):
    """
    Получение версии приложения.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - version: строковое значение версии.
    """
    # В БД содержится одна запись - получаем её
    # version = db.query(AppVersion.version).first()

    doc_info = (
        db.query(InfoDocuments)
        .filter_by(type=doc_type)
        .options(joinedload(InfoDocuments.rules))
        .first()
    )

    if not doc_info:
        logger.error(f"crud/main- get_documents_by_type. Документ `{doc_type}` не найден")
        return None

    rules_out = []
    for rule in doc_info.rules:
        rules_out.append(InfoDocumentsRulesOut(title=rule.title, description=rule.description))

    info_documents_out = InfoDocumentsOut(
        is_anchor=doc_info.is_anchor,
        type=doc_info.type,
        title=doc_info.title,
        description=doc_info.description,
        rules=rules_out
    )

    return info_documents_out


async def get_advs_count(db):
    """
    Получение версии приложения.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - version: строковое значение версии.
    """
    # В БД содержится одна запись - получаем её
    # version = db.query(AppVersion.version).first()

    advs_count = db.query(Ad).count()
    if not advs_count:
        logger.error(f"crud/main- get_advs_count. Не удалось получить количество объявлений Кликса")

    return advs_count


async def get_active_users_count(db):
    """
    Получение версии приложения.

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - version: строковое значение версии.
    """
    # В БД содержится одна запись - получаем её
    # version = db.query(AppVersion.version).first()

    active_users_count = db.query(User).filter(User.is_active).count()
    if not active_users_count:
        logger.error(f"crud/main- get_active_users_count. Не удалось получить количество пользователей Кликса")

    return active_users_count
