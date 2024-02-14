from uuid import UUID

from sqlalchemy.orm import Session

from app.db.db_models import AdPhotos
from app.logger import setup_logger

logger = setup_logger(__name__)

# Функция получения изображения по ее идентификатору
def get_image_by_uuid(db: Session, image_uuid: UUID):
    """
    Получение объекта изображения по идентификатору из БД.

    Параметры:
    - image_uuid: Идентификатор изображения.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - id: Идентификатор изображения
    - ad_id: Идентификатор связанного объявления
    - url: путь к изображению
    """
    db_image = db.query(AdPhotos).filter(AdPhotos.id == image_uuid).first()
    if db_image:
        return db_image
    else:
        logger.error(f"crud/image- get_image_by_uuid. Ошибка получения изображения")
        return False
