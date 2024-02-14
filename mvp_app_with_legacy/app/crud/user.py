import hashlib
import io
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional, List
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings, get_current_time2
from app.db.db_models import User, UserLocation, Ad, UserDevices, UserViews, CashWallet, WalletTransactions
from app.logger import setup_logger
from app.schemas import user as user_schemas
from app.schemas.ad import LocationOutModel, ItemsOutModel
from app.utils import security, exception
from app.utils.ad import validate_location
from app.utils.dependencies import oauth2_scheme, get_db
import os
import shutil
from PIL import Image
from pillow_heif import register_heif_opener
from app.db.db_models import UserPhoto
import httpx
logger = setup_logger(__name__)

def create_user(db: Session, user: user_schemas.UserCreate):
    if get_user_by_phone(db=db, phone=user.phone):
        logger.error(f"crud/user- create_user. Пользователь с номером {user.phone} уже существует")
        return False
    db_user = User(phone=user.phone,
                   name=user.name,
                   emailVerified=False,
                   phoneVerified=True,
                   password=security.hash_password(user.password),
                   createdAt=get_current_time2())
    db.add(db_user)
    db.commit()
    return True


def create_user_oauth(user: user_schemas.UserCreateOauth, db: Session):
    db_user = User(email=user.email,
                   name=user.name,
                   emailVerified=user.emailVerify,
                   googleId=user.googleId,
                   appleId=user.appleId,
                   phoneVerified=False,
                   createdAt=get_current_time2())

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def auth_user(username: str, password: str, db: Session):
    db_user = get_user_by_phone(db=db, phone=username)
    if not db_user:
        return False
    if not security.verify_password(password, db_user.password):
        return False
    db_user.lastLoginAt = get_current_time2()
    db.commit()
    return db_user


def change_password(user: User, new_password: str, db: Session):
    user.password = security.hash_password(new_password)
    db.commit()


def change_password_manually(
        user: User,
        current_password: str,
        new_password: str,
        db: Session
):
    if not security.verify_password(current_password, user.password):
        return False
    user.password = security.hash_password(new_password)
    db.commit()
    return True


def get_current_user(db: Session = Depends(get_db),
                     access_token: str = Depends(oauth2_scheme)):
    token_data = security.decode_access_token(access_token)
    user_id = token_data.get("sub")
    user = get_user_by_id(db=db, user_id=user_id)
    if not user:
        logger.error(f"crud/user- get_current_user. Пользователь не авторизован")
        raise exception.credentials_exception

    user.online_at = get_current_time2()
    if not user.online:
        user.online = True
        db.commit()
    return user


async def get_current_user_or_none(db: Session = Depends(get_db), access_token: str = Depends(oauth2_scheme)) -> \
Optional[User]:
    try:
        user = get_current_user(db, access_token)
        return user

    except Exception as e:
        return None


def get_user_by_id(db: Session, user_id: int):
    db_user = db.query(User).get(user_id)
    if db_user:
        check_user_online(db_user, db)
        return db_user
    else:
        logger.error(f"crud/user- get_user_by_id. Пользователь по id не найден")
        return False


def get_user_by_email(db: Session, email: str):
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        return db_user
    else:
        logger.error(f"crud/user- get_user_by_email. Пользователь по email не найден")
        return False


def get_user_by_phone(db: Session, phone: str):
    db_user = db.query(User).filter(User.phone == phone).first()
    if db_user:
        return db_user
    else:
        logger.error(f"crud/user- get_user_by_phone. Пользователь по phone не найден")
        return False


def get_user_by_google_id(db: Session, google_id: str):
    db_user = db.query(User).filter(User.googleId == google_id).first()
    if db_user:
        return db_user
    else:
        return False


def get_user_by_apple_id(db: Session, apple_id: str):
    db_user = db.query(User).filter(User.appleId == apple_id).first()
    if db_user:
        return db_user
    else:
        return False


def get_first_photo_id(photos):
    if photos:
        return photos[0].id
    return ''


def group_ads_by_status(status, user: User):
    ads_by_status = []
    i = 0

    for adv in user.ads:
        user_ad_location = {
            "address": adv.location.address,
            "full_address": adv.location.full_address,
            "detail": {
                "country": adv.location.country,
                "lat": adv.location.lat,
                "long": adv.location.long,
                "region": adv.location.region,
                "district": adv.location.district,
                "city": adv.location.city,
                "street": adv.location.street,
                "house": adv.location.house
            }
        }

        photos = get_first_photo_id(adv.photos)

        res = user_schemas.ItemsOutModel(
            id=adv.id,
            title=adv.title,
            description=adv.description,
            price=adv.price,
            location=LocationOutModel(**user_ad_location),
            photos=photos,
            favorite=False,
            created_at=str(adv.created_at)
        )

        if adv.status_id == status:
            ads_by_status.append(res)
            i += 1

    return ads_by_status


def update_phone(db: Session, user: user_schemas.UserChangePhone):
    db_user = get_user_by_phone(db=db, phone=user.old_phone)
    db_user.phone = user.new_phone
    db.commit()
    return True


async def edit_user_data(key, name, location, photo, delete_photo, db):
    # user = db.query(User).filter(User.id == key).first()
    user = db.query(User).get(key)
    errors = {}

    if name:
        user.name = name

    if location and user.location:
        location_data = json.loads(location)
        invalid_location = validate_location(location_data)
        if invalid_location:  # Ошибки местоположения
            errors['location'] = invalid_location
        if errors:
            logger.error(f"crud/user- edit_user_data. Некорректное местоположение")
            raise HTTPException(status_code=400, detail=errors)

        user.location.address = location_data["address"]
        user.location.full_address = location_data["full_address"]
        user.location.country = location_data['detail']['country']
        user.location.lat = location_data['detail']['lat']
        user.location.long = location_data['detail']['long']
        user.location.region = location_data['detail']['region']
        user.location.district = location_data['detail']['district']
        user.location.city = location_data['detail']['city']
        user.location.street = location_data['detail']['street']
        user.location.house = location_data['detail']['house']

    elif location and not user.location:
        location_data = json.loads(location)
        invalid_location = validate_location(location_data)
        if invalid_location:  # Ошибки местоположения
            errors['location'] = invalid_location
        if errors:
            logger.error(f"crud/user- edit_user_data. Некорректное местоположение")
            raise HTTPException(status_code=400, detail=errors)

        user_location = UserLocation(
            address=location_data['address'],
            full_address=location_data['full_address'],
            country=location_data['detail']['country'],
            lat=location_data['detail']['lat'],
            long=location_data['detail']['long'],
            region=location_data['detail']['region'],
            district=location_data['detail']['district'],
            city=location_data['detail']['city'],
            street=location_data['detail']['street'],
            house=location_data['detail']['house']
        )

        user.location = user_location
        db.add(user)

    if photo:
        await save_user_photo(photo, key, db)

    if delete_photo and not photo:
        await delete_user_photo(db, key)

    user.updatedAt = get_current_time2()
    db.commit()
    db.refresh(user)
    if not user.photo:
        user_photo = None
    else:
        user_photo = user.photo.id

    user_location = user.location.to_dict() if user.location else None

    return user.name, user_location, user_photo


def get_user_image_by_uuid(db: Session, image_uuid: uuid.UUID):
    """
    Получение объекта изображения по идентификатору из БД.

    Параметры:
    - image_uuid: Идентификатор изображения.
    - db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - id: Идентификатор изображения
    - url: путь к изображению
    """
    db_image = db.query(UserPhoto).filter(UserPhoto.id == image_uuid).first()
    if db_image:
        return db_image
    else:
        return False


async def upload_user_photo(photo, user_id, db):
    if photo:
        result = await save_user_photo(photo, user_id, db)
    else:
        result = False
    return result


async def save_user_photo(image, user_id, db):
    try:
        image_content = image.file.read()
        image_hash = hashlib.md5(image_content).hexdigest()

        road = "/" + "/".join([str(image_hash[i] + str(image_hash[i + 1])) for i in range(0, 7, 2)])
        road += f"/{uuid.uuid4()}"

        # Register opener for HEIF/HEIC format
        register_heif_opener()

        orientation_value = get_image_orientation(image_content)
        im = Image.open(io.BytesIO(image_content))
        # Convert to RGB if needed
        im = im.convert("RGB")

        if orientation_value == 3:
            im = im.rotate(180, expand=True)
        elif orientation_value == 6:
            im = im.rotate(-90, expand=True)
        elif orientation_value == 8:
            im = im.rotate(90, expand=True)

        await save_user_image_square_thumbnails(image=im, road=road)
        await write_user_image_road(db=db, user_id=user_id, image_road=road)

    except Exception as e:
        print('error', str(e))
        logger.error(f"crud/user- save_user_photo. Ошибка сохранения фото пользователя")
        return False
    return True


async def save_user_image_square_thumbnails(image, road):
    width, height = image.size
    if width > height:
        cropped = (width - height) / 2
        im = image.crop((cropped, 0, width - cropped, height))
        im = im.resize((300, 300))
    elif width < height:
        cropped = (height - width) / 2
        im = image.crop((0, cropped, width, height - cropped))
        im = im.resize((300, 300))
    else:
        im = image.resize((300, 300))
    await save_file_in_folder(image=im, road=road, resolution="300x300")


async def write_user_image_road(db: Session, user_id: int, image_road: str):
    user_images = db.query(UserPhoto).filter(UserPhoto.user_id == user_id).all()

    for user_image in user_images:
        user_url = f"./files{user_image.url}/"
        db.query(UserPhoto).where(UserPhoto.id == user_image.id).delete()
        db.commit()

        if os.path.exists(user_url):
            shutil.rmtree(os.path.dirname(user_url))

    image_road_object = UserPhoto(url=image_road, user_id=user_id, id=uuid.uuid4())
    db.add(image_road_object)
    db.commit()
    return True


async def delete_user_photo(db: Session, user_id: int):
    user_images = db.query(UserPhoto).filter(UserPhoto.user_id == user_id).all()

    for user_image in user_images:
        user_url = f"./files{user_image.url}/"
        db.query(UserPhoto).where(UserPhoto.id == user_image.id).delete()
        db.commit()

        if os.path.exists(user_url):
            shutil.rmtree(os.path.dirname(user_url))


async def save_file_in_folder(image, road, resolution):
    Path(f"./files/{road}").mkdir(parents=True, exist_ok=True)
    image.save(f"./files/{road}/{resolution}.webp", format="webp")


def get_image_orientation(image_content):
    orientation_value = 1  # Default orientation (normal)
    with io.BytesIO(image_content) as f:
        im = Image.open(f)
        if hasattr(im, '_getexif'):
            exif = im._getexif()
            if exif is not None:
                orientation_tag = 274  # EXIF tag for orientation
                orientation_value = exif.get(orientation_tag, 1)
    return orientation_value


async def add_or_remove_favorites(user_id: int, ad_id: uuid, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.error(f"crud/user- add_or_remove_favorites. Пользователь не найден")
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if ad is None:
        logger.error(f"crud/user- add_or_remove_favorites. Объявление не найдено")
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    if ad in user.favorite_advs:
        user.favorite_advs.remove(ad)
        action = False
    else:
        user.favorite_advs.append(ad)
        action = True
    db.commit()

    return {"favorite": action}


async def add_list_favorites(user_id: int, ad_list: List[uuid.UUID], db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.error(f"crud/user- add_list_favorites. Пользователь не найден")
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    added_ads = []
    # already_added_ads = []
    # not_added_ads = []
    for ad_id in ad_list:
        ad = db.query(Ad).get(ad_id)
        if ad:
            if ad not in user.favorite_advs:
                added_ads.append(ad)
                user.favorite_advs.append(ad)
        #     if ad in user.favorite_advs:
        #         already_added_ads.append(ad_id)
        # else:
        #     not_added_ads.append(ad_id)

    db.commit()

    added_ads_response = []
    for ad in added_ads:
        if ad.photos:
            photos = ad.photos[0].id
        else:
            photos = ''

        item = ItemsOutModel(
            id=ad.id,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            location=ad.location.to_dict(),
            photos=photos,
            favorite=True,  # Предполагаем, что объявление добавлено в избранное
            status=str(ad.status.status),
            created_at=str(ad.created_at)
        )
        added_ads_response.append(item)

    return {"items": added_ads_response}
    # return { "items": added_ads_response, "already_added_ads": already_added_ads, "not_added_ads": not_added_ads }


async def change_notification_auth(unique_id: str, is_auth: bool):
    if settings.MODE == "TEST":
        return

    data = {
        "unique_id": unique_id,
        "is_auth": is_auth
    }
    NOTIFICATION_TOKEN_LINK = settings.NOTIFICATION_TOKEN_URL + settings.NOTIFICATION_TOKEN_PATH
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(NOTIFICATION_TOKEN_LINK, json=data)
            return response
    except:
        logger.error(f"crud/user- change_notification_auth. Ошибка соединения")
        raise HTTPException(status_code=404, detail={
            "msg": "Ошибка соединения"
        })


async def delete_all_notification_auth(user_id: int, refresh_token: str, db):
    user_devices_list = db.query(UserDevices).filter(
        UserDevices.user_id == user_id,
        UserDevices.token != refresh_token
    ).all()
    responses_list = []
    is_auth = False

    unique_id_list = [user_device.uniqueId for user_device in user_devices_list]

    for unique_id in unique_id_list:
        data = {
            "unique_id": unique_id,
            "is_auth": is_auth
        }
        NOTIFICATION_TOKEN_LINK = settings.NOTIFICATION_TOKEN_URL + settings.NOTIFICATION_TOKEN_PATH
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(NOTIFICATION_TOKEN_LINK, json=data)
                responses_list.append(response)
        except:
            logger.error(f"crud/user- delete_all_notification_auth. Ошибка соединения unique_id: {unique_id}")
            raise HTTPException(status_code=404, detail={
                "msg": "Ошибка соединения"
            })
    return responses_list


def check_user_online(db_user, db):
    if db_user.online:
        now = get_current_time2()
        if not db_user.online_at:
            db_user.online = False
            db.commit()
        else:
            db_user_online_at = db_user.online_at
            db_user_expire_at = db_user_online_at + timedelta(minutes=settings.ONLINE_USER_EXPIRE_MINUTES)
            if db_user_expire_at < now:
                db_user.online = False
                db.commit()


def inc_user_views(db_user, db):
    try:
        db_user.views += 1
        db.commit()
        return True
    except:
        logger.error(f"crud/user- inc_user_views. Ошибка добавления просмотра для user_id: {db_user.id}")
        return False


async def inc_unique_views(current_user, device_id, user_id, db_user, db):
    if current_user:
        user_views_auth = db.query(UserViews).filter(UserViews.device_id == device_id,
                                                     UserViews.user_viewed_id == user_id,
                                                     UserViews.user_id == current_user.id).first()

        # Если нет записей с авторизацией, проверям есть ли записи без авторизации для текущего устройства
        if not user_views_auth:
            user_views_no_auth = db.query(UserViews).filter(UserViews.device_id == device_id,
                                                            UserViews.user_viewed_id == user_id,
                                                            UserViews.user_id == None).first()

            # Если нет записей БЕЗ авторизации, то создаем новую и увеличиваем просмотры
            if not user_views_no_auth:
                # CREATE NEW views record without auth => then =>
                new_user_view = UserViews(id=uuid.uuid4(),
                                          user_id=current_user.id,
                                          user_viewed_id=user_id,
                                          device_id=device_id,
                                          created_at=get_current_time2())
                db.add(new_user_view)
                db.commit()

                inc_user_views(db_user, db)

            # Если существует запись БЕЗ авторизации, добавляем в эту запись авторизацию
            else:
                user_views_no_auth.user_id = current_user.id
                db.commit()

        # Если запись с авторизацией уже есть, то пропускаем
        else:
            pass

    # Если запрос без авторизации
    else:
        # Проверяем существуют ли записи без учета авторизации для текущего устройства
        user_views_no_auth = db.query(UserViews).filter(UserViews.device_id == device_id,
                                                        UserViews.user_viewed_id == user_id).first()
        # Если нет записей, то создаем новую и увеличиваем просмотры
        if not user_views_no_auth:
            # CREATE NEW views record without auth => then =>
            new_user_view = UserViews(id=uuid.uuid4(),
                                      user_viewed_id=user_id,
                                      device_id=device_id,
                                      created_at=get_current_time2())
            db.add(new_user_view)
            db.commit()

            inc_user_views(db_user, db)

        # Если нашли хоть одну запись для текущего устройства, то пропускаем
        else:
            pass


# Создание денежного кошелька
def create_cash_wallet(user_id, balance, db):
    cash_wallet = CashWallet(
        id=uuid.uuid4(),
        user_id=user_id,
        balance=balance
    )
    db.add(cash_wallet)
    db.commit()

    return cash_wallet


# Функция 100% кэшбека бонусами при пополнении баланса
def multiply_bonus(cash, cash_multiplier):
    balance = cash * cash_multiplier
    return balance


def create_transaction(user_id, cash_wallet_id, cash_wallet_balance, cash_sign, service, deposit, db):

    new_transaction = WalletTransactions(
        id=uuid.uuid4(),
        user_id=user_id,
        cash_wallet_id=cash_wallet_id,
        cash=cash_wallet_balance,
        cash_sign=cash_sign,
        service=service,
        deposit=deposit,
        created_at=get_current_time2(),
    )
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return new_transaction
