import datetime
import json
from calendar import timegm

from jose import jwt
from sqlalchemy.orm import Session

from app.db.db_models import UserDevices
from app.logger import setup_logger, setup_logger_refresh
from app.utils import exception
logger = setup_logger_refresh(__name__)

def refresh_token_verification(refresh_token: str, db: Session):
    refresh_data = jwt.get_unverified_claims(refresh_token)
    now = timegm(datetime.datetime.utcnow().utctimetuple())
    exp, user_id = refresh_data['exp'], refresh_data['sub']
    logger.info(f"==================================================================")
    logger.info(f"utils/devices- refresh_token_verification. Пользователь: {user_id}")
    logger.info(f"utils/devices- refresh_token_verification. Устройство из Токена: {refresh_data['device']}")
    logger.info(f"utils/devices- refresh_token_verification. РефрешТокен: {refresh_token}")
    # Проверка токена на существование
    db_devices = db.query(UserDevices).filter(UserDevices.user_id == int(user_id)).all()
    if db_devices:
        for device in db_devices:
            logger.info(f"utils/devices- refresh_token_verification. Устройство: {device.uniqueId}. refresh_token: {device.token}")
            if device.token == refresh_token and now > exp:
                db.query(UserDevices).where(UserDevices.token == refresh_token).delete()
                db.commit()
                logger.error(f"utils/devices- refresh_token_verification. Рефреш токен найден, но просрочен: {refresh_token}. user_id: {user_id}")
                return False
            elif device.token == refresh_token and now < exp:
                logger.info(f"utils/devices- refresh_token_verification. Подтвержденное устройство: {device.uniqueId}")
                logger.info(f"utils/devices- refresh_token_verification. РефрешТокен Прошел Проверку: {refresh_token}")
                return True
    else:
        logger.info(f"utils/devices- refresh_token_verification. Устройства пользователя не найдены!!!")
    logger.error(f"utils/devices- refresh_token_verification. Рефреш токен НЕ найден: {refresh_token}. user_id: {user_id}")
    return False


def check_device_unique_id():
    pass


def json_parse(device: str):
    try:
        res = json.loads(device)
        return res
    except Exception:
        logger.error(f"utils/devices- json_parse: Непредвиденная ошибка")
        raise exception.unexpected_error
