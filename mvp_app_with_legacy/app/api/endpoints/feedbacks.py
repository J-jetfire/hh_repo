from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.crud.ad import get_adv_data
from app.crud.feedback import create_feedback_object, update_user_fields_on_feedback, delete_user_feedback, \
    get_paginated_feedback_advs, get_same_feedback
from app.crud.user import get_current_user
from app.db.db_models import User, DealStateEnum
from app.logger import setup_logger
from app.schemas.ad import PaginatedItems
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackOut
from app.utils.dependencies import get_db

logger = setup_logger(__name__)
router = APIRouter(prefix="/feedback", tags=["FeedBack"])


@router.post("/create", summary="Create Feedback", status_code=201, response_model=FeedbackResponse)
async def create_feedback(data: FeedbackCreate, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """
    Создание отзыва

    Параметры:
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Модель отзыва
    """
    try:
        if data.owner_id == current_user.id:
            logger.error(f"api/endpoints/feedbacks- create_feedback. Невозможно оставить отзыв на самого себя: {current_user.id}")
            raise HTTPException(status_code=400, detail=f'Невозможно оставить отзыв на самого себя')

        # проверка, существует ли отзыв с такими же данными
        is_feedback_exists = get_same_feedback(current_user.id, data.owner_id, data.adv_id, db)

        if is_feedback_exists:
            logger.error(f"api/endpoints/feedbacks- create_feedback. Вы уже оставляли отзыв на это объявление: {data.adv_id}")
            raise HTTPException(status_code=400, detail=f'Вы уже оставляли отзыв на это объявление')

        # Проверяем объявление на наличие и совпадение входных данных пользователя
        adv = get_adv_data(data.adv_id, db)

        if not adv:
            logger.error(f"api/endpoints/feedbacks- create_feedback. Объявление не найдено: {data.adv_id}")
            raise HTTPException(status_code=404, detail=f'Объявление не найдено')

        if adv.user_id != data.owner_id:
            logger.error(f"api/endpoints/feedbacks- create_feedback. Некорректные данные владельца объявления: {data.owner_id}")
            raise HTTPException(status_code=400, detail=f'Некорректные данные владельца объявления')

        if data.state is not None and data.state not in [state.value for state in DealStateEnum]:
            logger.error(f"api/endpoints/feedbacks- create_feedback. Некорректный статус сделки: {data.state}")
            raise HTTPException(status_code=400, detail=f'Некорректный статус сделки')

        if len(data.text) > 2000:
            logger.error(f"api/endpoints/feedbacks- create_feedback. Текст отзыва не должен превышать 2000 символов")
            raise HTTPException(status_code=400, detail=f'Текст отзыва не должен превышать 2000 символов')

        # Создаем объект отзыва и оценки в БД
        new_feedback = create_feedback_object(current_user.id, data, db)

        # Обновляем поля пользователя на основе нового отзыва
        update_user_fields_on_feedback(new_feedback.owner_id, new_feedback.rating, db, increase=True)

        response = {
            "id": new_feedback.id,
            "user_id": new_feedback.user_id,
            "owner_id": new_feedback.owner_id,
            "adv_id": new_feedback.adv_id,
            "rating": new_feedback.rating,
            "text": new_feedback.text,
            "state": new_feedback.state,
            "created_at": str(new_feedback.created_at)
        }
        return response

    except HTTPException as http_exc:
        raise http_exc

    except Exception as e:
        logger.error(f"Ошибка публикации отзыва: {str(e)}")
        raise HTTPException(status_code=400, detail=f'Ошибка публикации отзыва')


@router.get("/user/{owner_id}", summary="Get Feedbacks by Owner ID", response_model=List[FeedbackOut])
async def get_feedbacks_by_owner_id(owner_id: int, db: Session = Depends(get_db)):
    """
    Выдача всех отзывов пользователя по его идентификатору

    Параметры:
    - owner_id (int): Идентификатор пользователя.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Данные владельца отзывов
    - Список всех отзывов пользователя
    """
    try:
        owner = db.query(User).get(owner_id)
        if not owner:
            logger.error(f"api/endpoints/feedbacks- get_feedbacks_by_owner_id. Пользователь не найден: {owner_id}")
            raise HTTPException(status_code=404, detail='Пользователь не найден')

        feedbacks_list = [
            {
                "id": str(feedback.id),
                "user": {
                    "id": feedback.user_left.id,
                    "name": feedback.user_left.name,
                    "photo": str(feedback.user_left.photo.id) if feedback.user_left.photo else ''
                },
                "adv": {
                    "id": str(feedback.adv.id),
                    "title": feedback.adv.title
                },
                "rating": feedback.rating,
                "text": feedback.text,
                "state": feedback.state,
                "created_at": str(feedback.created_at)
            }
            for feedback in owner.feedbacks_received
        ]

        # owner_data = {
        #     "id": owner.id,
        #     "name": owner.name,
        #     "photo": str(owner.photo.id) if owner.photo else '',
        #     "is_active": owner.is_active,
        #     "is_blocked": owner.is_blocked,
        #     "rating": owner.rating,
        #     "feedback_count": owner.feedback_count
        # }

        # return {"owner": owner_data, "feedback": feedbacks_list}
        return feedbacks_list

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"api/endpoints/feedbacks- get_feedbacks_by_owner_id. Ошибка при получении отзывов: {str(e)}")
        raise HTTPException(status_code=500, detail=f'Ошибка при получении отзывов: {str(e)}')


# DELETE feedback by id and auth
@router.delete("/{feedback_id}", summary="Delete Feedback by ID", status_code=202,
               dependencies=[Depends(get_current_user)])
async def delete_feedback(feedback_id: UUID, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """
    Удаление СВОЕГО отзыва авторизованным пользователем по идентификатору

    Параметры:
    - feedback_id (UUID): Идентификатор отзыва
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - Объект success: True/False
    """
    try:
        result = delete_user_feedback(current_user.id, feedback_id, db)
        return {"success": result}

    except Exception as e:
        logger.error(f"api/endpoints/feedbacks- delete_feedback. Ошибка удаления отзыва: {str(e)}")
        raise HTTPException(status_code=400, detail=f'Ошибка удаления отзыва: {str(e)}')


@router.get("/all")
async def all_feedbacks_for_auth_user(
        current_user: User = Depends(get_current_user)
):
    try:
        if current_user.feedbacks_left:
            feedbacks_list = [
                {
                    "id": str(feedback.id),
                    "user": {
                        "id": feedback.user_received.id,
                        "name": feedback.user_received.name,
                        "photo": str(feedback.user_received.photo.id) if feedback.user_received.photo else ''
                    },
                    "adv": {
                        "id": str(feedback.adv.id),
                        "title": feedback.adv.title
                    },
                    "rating": feedback.rating,
                    "text": feedback.text,
                    "state": feedback.state,
                    "created_at": str(feedback.created_at)
                }
                for feedback in current_user.feedbacks_left
            ]

            return feedbacks_list
        else:
            return []

    except Exception as e:
        logger.error(f"api/endpoints/feedbacks- all_feedbacks_for_auth_user. Ошибка при получении отзывов: {str(e)}")
        raise HTTPException(status_code=500, detail=f'Ошибка при получении отзывов: {str(e)}')


@router.get('/items/{user_id}', summary="Get all Advertisements of User for feedback", status_code=200,
            response_model=PaginatedItems)
async def get_all_users_ads_for_feedback(
        user_id: int,
        search: str = None,
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Получение объявлений с применением сортировки, пагинации и фильтров.

    Параметры:
    - sort: Сортировка.
    - page: Страница пагинации.
    - limit: Кол-во объявлений на одной странице.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
    - current_user (User): Объект пользователя (если авторизован)

    Возвращает:
    - PaginatedItems:
        - total: Кол-во объявлений.
        - items: Список объявлений.
    """

    if current_user.id == user_id:
        logger.error(f"api/endpoints/feedbacks- get_all_users_ads_for_feedback. Невозможно оставить отзыв на самого себя: {user_id}")
        raise HTTPException(status_code=400, detail="Невозможно оставить отзыв на самого себя")

    ad_list = get_paginated_feedback_advs(search, sort, page, limit, user_id, db)

    return ad_list
