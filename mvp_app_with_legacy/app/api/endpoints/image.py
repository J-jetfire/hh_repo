from fastapi import APIRouter, Depends, HTTPException, responses
from uuid import UUID
from sqlalchemy.orm import Session
from pathlib import Path

from app.logger import setup_logger
from app.utils.dependencies import get_db
from app.crud import image as image_crud
from app.schemas import ad as ad_schema


router = APIRouter(prefix="/images", tags=["Images"])
logger = setup_logger(__name__)

# Получение изображения по идентификатору с учетом разрешения(resolution) изображения
@router.get("/{resolution}/{uuid}", summary="Get Image By UUID", response_class=responses.FileResponse)
async def get_image(resolution: ad_schema.PostImageResolutions, uuid: UUID, db: Session = Depends(get_db)):
    """
    Получение изображения по разрешению и идентификатору.

    Параметры:
    - resolution: Резрешение изображения.
    - uuid: Идентификатор изображения.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Изображение, как файл .webp
    """

    db_photo = image_crud.get_image_by_uuid(db=db, image_uuid=uuid)
    # Если фото не найдено, выводим ошибку
    if not db_photo:
        logger.error(f"api/endpoints/image- get_image. Не удалось получить изображение")
        raise HTTPException(404)
    # Формируем путь(ссылку) для выдачи изображения
    image = f"./files{db_photo.url}/{resolution.value}.webp"
    # Если в данной директории нет файла, выводим ошибку
    if not Path(image).is_file():
        logger.error(f"api/endpoints/image- get_image. Изображение не найдено в хранилище")
        raise HTTPException(404)
    return image
