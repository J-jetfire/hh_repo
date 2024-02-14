from datetime import datetime
from typing import List

from fastapi import Depends, HTTPException, APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.logger import setup_logger
from app.utils.dependencies import get_db
from app.crud.user import get_current_user as get_user, check_user_online
from app.db.db_models import User, UserSubscription


router = APIRouter(prefix="/subscription", tags=["Subscription"])
logger = setup_logger(__name__)

class UserSubscriptionModel(BaseModel):
    id: int
    name: str
    photo: str | None = None
    rating: float
    online: bool
    online_at: str | None = None
    is_active: bool
    is_blocked: bool


def subscribe_user(subscriber: int, subscribed_to: int, db: Session):
    # Проверяем подписаны ли уже на этого пользователя
    subscription = db.query(UserSubscription).where(UserSubscription.subscriber_id == subscriber, UserSubscription.subscribed_to_id == subscribed_to).one_or_none()
    if subscription:
        print(f"Subscriber({subscriber}) already subscribed to user({subscribed_to})")
        logger.info(f"api/endpoints/subscription- subscribe_user. Пользователь: {subscriber} уже подписан на: {subscribed_to}")
        return subscription

    # Проверяем существует ли пользователь на которого подписываемся
    user_exists = db.query(User).get(subscribed_to)
    if not user_exists:
        logger.info(f"api/endpoints/subscription- subscribe_user. Пользователь `{subscribed_to}` не существует.")
        return None

    """Подписка пользователя на другого пользователя"""
    subscription = UserSubscription(
        subscriber_id=subscriber,
        subscribed_to_id=subscribed_to,
        created_at=datetime.now()
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def unsubscribe_user(subscriber: int, subscribed_to: int, db: Session):
    """Отписка от пользователя"""
    subscription = db.query(UserSubscription).where(UserSubscription.subscriber_id==subscriber, UserSubscription.subscribed_to_id==subscribed_to).one_or_none()
    if subscription:
        db.delete(subscription)
        db.commit()
        return True
    else:
        logger.info(f"api/endpoints/subscription- unsubscribe_user. Пользователь `{subscriber}` не был подписан на `{subscribed_to}`")
        return False


@router.post("/subscribe/{user_id}", status_code=202, response_model=UserSubscriptionModel)
async def subscribe_user_by_id(
        user_id: int,
        current_user: User = Depends(get_user),
        db: Session = Depends(get_db)
):

    if current_user.id == user_id:
        logger.error(f"api/endpoints/subscription- subscribe_user_by_id. Нельзя подписаться на самого себя. user_id: {current_user.id}")
        raise HTTPException(status_code=400, detail="Нельзя подписаться на самого себя")

    subscription = subscribe_user(current_user.id, user_id, db)

    if subscription is None:
        logger.error(f"api/endpoints/subscription- subscribe_user_by_id. Такого пользователя не существует. user_id: {user_id}")
        raise HTTPException(status_code=400, detail="Такого пользователя не существует")

    check_user_online(subscription.subscribed_to, db)

    return {
        "id": subscription.subscribed_to.id,
        "name": subscription.subscribed_to.name,
        "photo": str(subscription.subscribed_to.photo.id) if subscription.subscribed_to.photo else None,
        "rating": subscription.subscribed_to.rating,
        "online": subscription.subscribed_to.online,
        "online_at": str(subscription.subscribed_to.online_at) if subscription.subscribed_to.online_at else None,
        "is_active": subscription.subscribed_to.is_active,
        "is_blocked": subscription.subscribed_to.is_blocked
    }


@router.post("/unsubscribe/{user_id}", status_code=202)
async def unsubscribe_user_by_id(
    user_id: int,
    current_user: User = Depends(get_user),
    db: Session = Depends(get_db)
):

    if current_user.id == user_id:
        logger.error(f"api/endpoints/subscription- unsubscribe_user_by_id. Нельзя отписаться от самого себя. user_id: {user_id}")
        raise HTTPException(status_code=400, detail="Нельзя отписаться от самого себя")

    subscription = unsubscribe_user(current_user.id, user_id, db)
    return subscription


@router.get("/get", status_code=200,  response_model=List[UserSubscriptionModel])
async def get_subscriptions(
    current_user: User = Depends(get_user),
    db: Session = Depends(get_db)
):
    response = []
    if current_user.subscriptions:
        for subscription in current_user.subscriptions:

            check_user_online(subscription.subscribed_to, db)

            subscription_user = {
                "id": subscription.subscribed_to.id,
                "name": subscription.subscribed_to.name,
                "photo": str(subscription.subscribed_to.photo.id) if subscription.subscribed_to.photo else None,
                "rating": subscription.subscribed_to.rating,
                "online": subscription.subscribed_to.online,
                "online_at": str(subscription.subscribed_to.online_at) if subscription.subscribed_to.online_at else None,
                "is_active": subscription.subscribed_to.is_active,
                "is_blocked": subscription.subscribed_to.is_blocked,
            }
            response.append(subscription_user)

    return response
