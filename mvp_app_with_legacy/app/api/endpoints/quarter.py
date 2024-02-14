from fastapi import APIRouter
from app.utils.quarter import get_yearly_quarters
from app.utils import exception
from app.schemas import car as car_schemas


router = APIRouter(prefix="/quarter", tags=["Quarters Data"])


# API получения кварталов для текущей даты
@router.get("", summary="Get quarters",response_model=car_schemas.Suggestion, status_code=200,
            responses={400: exception.custom_errors("Bad Request", [{"msg": "Invalid data"}])})
async def get_quarters():
    """
    Получение кварталов для текущей даты

    Возвращает:
    - name: quarter.
    - values: Список строк со значениями кварталов.
    - completedFields: null.
    """
    # Вызываем функцию получения кварталов
    yearly_quarters = get_yearly_quarters()
    return yearly_quarters
