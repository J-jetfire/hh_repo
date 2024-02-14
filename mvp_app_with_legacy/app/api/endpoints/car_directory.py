from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud.car import car_suggestion
from app.logger import setup_logger
from app.schemas import car as car_schemas
from app.utils import exception
from app.utils.dependencies import get_db

router = APIRouter(prefix="/car", tags=["Car Data"])
logger = setup_logger(__name__)

@router.get("", summary="Car fields",
            response_model=car_schemas.Suggestion, status_code=200,
            responses={400: exception.custom_errors("Bad Request", [{"msg": "Invalid data"}])})
async def car_directory(car: car_schemas.Car = Depends(),
                        db: Session = Depends(get_db)):
    """
    Получение доп.полей для автомобилей.

    Параметры:
    - car (Car): Тело запроса.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - name: Наименование поля модели Car.
    - values: Список строк с доступными значениями.
    - completedFields: null or list of objects.
    """

    suggestion = car_suggestion(db=db, car=car)
    if not suggestion:
        logger.error(f"api/endpoints/car_directory- car_directory. Ошибка получения данных")
        raise HTTPException(status_code=400, detail={"msg": "Invalid data"})
    return suggestion
