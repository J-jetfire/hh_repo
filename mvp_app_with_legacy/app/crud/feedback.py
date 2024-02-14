import uuid
from datetime import datetime
from typing import Union

from sqlalchemy import or_

from app.db.db_models import User, FeedBackUsers, Ad, DealStateEnum
from app.schemas.ad import ItemsOutModel, PaginatedItems


def create_feedback_object(user_id, data, db):
    new_feedback = FeedBackUsers(
        id=uuid.uuid4(),
        user_id=user_id,
        owner_id=data.owner_id,
        adv_id=data.adv_id,
        rating=data.rating,
        text=data.text,
        state=DealStateEnum(data.state).value if data.state else None,
        created_at=datetime.now()
    )

    db.add(new_feedback)
    db.commit()
    return new_feedback


def update_user_fields_on_feedback(user_id, new_rating, db, increase):
    user = db.query(User).get(user_id)
    if user:
        if increase:
            user.feedback_count += 1
            user.rating_sum += new_rating
        else:
            user.feedback_count -= 1
            user.rating_sum -= new_rating

        if user.feedback_count > 0:
            user.rating = round(user.rating_sum / user.feedback_count, 1)
        else:
            user.rating = 0

        db.commit()


def delete_user_feedback(user_id, feedback_id, db) -> Union[bool, None]:
    feedback = db.query(FeedBackUsers).get(feedback_id)

    if feedback and feedback.user_id == user_id:
        owner_id, rating = feedback.owner_id, feedback.rating
        db.delete(feedback)
        db.commit()
        update_user_fields_on_feedback(owner_id, rating, db, increase=False)
        return True

    return False


def get_paginated_feedback_advs(search, sort, page, limit, current_user_id, db):
    offset = (page - 1) * limit  # Получаем значение смещения для пагинации

    ads, total = get_feedback_advs_query(search, sort, limit, offset, current_user_id, db)

    ad_list = []
    for ad in ads:
        photos = ad.photos[0].id if ad.photos else ''
        if current_user_id is not None:
            favorite = current_user_id in [user.id for user in ad.favorited_by]
        else:
            favorite = False

        ad_out = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict() if ad.location else {},
            photos=photos,
            favorite=favorite,
            status=ad.status.status,
            created_at=str(ad.created_at)
        )
        ad_list.append(ad_out)

    return PaginatedItems(total=total, items=ad_list)


def get_feedback_advs_query(search, sort, limit, offset, user_id, db):
    available_statuses = [3, 4, 5]  # Статусы объявлений для выдачи (3-active, 4-archived, 5-blocked)

    query = db.query(Ad).filter(or_(Ad.status_id == val for val in available_statuses))

    query = query.filter(Ad.user_id == user_id)

    sort_column = (  # Сортируем объявления по значению sort
        Ad.created_at.asc() if sort == 'date_asc' else
        Ad.created_at.desc() if sort == 'date_desc' else
        Ad.price.asc() if sort == 'price_asc' else
        Ad.price.desc() if sort == 'price_desc' else
        Ad.created_at.desc()
    )

    # Если получено поле поиска, то применяем поиск
    if search:
        search = search.strip()  # Remove leading/trailing whitespaces
        search_clause = or_(
            Ad.title.ilike(f'%{search}%'),
            Ad.description.ilike(f'%{search}%')
        )
        query = query.filter(search_clause)

    query = query.order_by(sort_column)

    # Получаем общее кол-во полученных записей и применяем пагинацию
    total = query.count()
    ads = query.offset(offset).limit(limit).all()
    return ads, total


def get_same_feedback(current_user_id, data_owner_id, data_adv_id, db):
    query = db.query(FeedBackUsers).filter_by(user_id=current_user_id, owner_id=data_owner_id, adv_id=data_adv_id).all()
    return True if query else False
