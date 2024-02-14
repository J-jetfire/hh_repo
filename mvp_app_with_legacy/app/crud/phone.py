import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.db_models import User, PhoneCall
from app.logger import setup_logger

logger = setup_logger(__name__)

def check_phone_blocking(phone: str, db: Session):
    db_phone = db.query(PhoneCall).filter(PhoneCall.phone == phone).one_or_none()
    time_now = datetime.datetime.utcnow()
    if db_phone:
        first_block_time = db_phone.last_call + datetime.timedelta(
            minutes=settings.FIRST_BLOCK_CALL_MINUTES)
        if db_phone.count_calls == 1 and first_block_time > time_now:
            res = str((first_block_time +
                       datetime.timedelta(hours=3) +
                       datetime.timedelta(minutes=1)).time())[0:5]
            logger.info(f"crud/phone- check_phone_code. Первая блокировка, попробуйте в {res} по МСК")
            raise HTTPException(status_code=404, detail={
                "msg": f"Первая блокировка, попробуйте в {res} по МСК"
            })

        second_block_time = db_phone.last_call + datetime.timedelta(
            minutes=settings.SECOND_BLOCK_CALL_MINUTES)
        if db_phone.count_calls >= 2 and second_block_time > time_now:
            res = str((second_block_time +
                       datetime.timedelta(hours=3) +
                       datetime.timedelta(minutes=1)).time())[0:5]
            logger.info(f"crud/phone- check_phone_code. Вторая блокировка, попробуйте в {res} по МСК")
            raise HTTPException(status_code=404, detail={
                "msg": f"Вторая блокировка, попробуйте в {res} по МСК"
            })
    else:
        return True


def create_phone_call(phone: str, verification_code: str, db: Session):
    db_call = db.query(PhoneCall).filter(PhoneCall.phone == phone).one_or_none()
    if db_call:
        db_call.verification_code = verification_code
        db_call.phone_validate = False
        db_call.count_calls += 1
        db_call.count_entered_codes = 0
        db_call.last_call = datetime.datetime.utcnow()
    else:
        new_db_call = PhoneCall(phone=phone,
                                phone_validate=False,
                                verification_code=verification_code,
                                last_call=datetime.datetime.utcnow())
        db.add(new_db_call)
    db.commit()
    return True


def check_phone_code(phone: str, verification_code: str, db: Session):
    time_limit = datetime.datetime.utcnow() - datetime.timedelta(
        minutes=settings.CALL_CODE_TIME_MINUTE)
    # 404 only not success code
    db_phone_call = db.query(PhoneCall).filter(
        PhoneCall.phone == phone).first()
    if not db_phone_call:
        logger.error(f"crud/phone- check_phone_code. Ошибка БД")
        raise HTTPException(status_code=400, detail={
            "msg": "Ошибка бд"
        })
    if db_phone_call.count_entered_codes >= 5:
        logger.info(f"crud/phone- check_phone_code. Кол-во попыток ввода кода исчерпано")
        raise HTTPException(status_code=409, detail={
            "msg": "Кол-во попыток ввода кода исчерпано"
        })
    if db_phone_call.verification_code != verification_code:
        db_phone_call.count_entered_codes += 1
        db.commit()
        logger.info(f"crud/phone- check_phone_code. Неверный код")
        raise HTTPException(status_code=404, detail={
            "msg": "Неверный код"
        })
    if db_phone_call.phone_validate:
        logger.info(f"crud/phone- check_phone_code. Код уже использован")
        raise HTTPException(status_code=400, detail={
            "msg": "Код уже использован"
        })
    if db_phone_call.last_call < time_limit:
        logger.info(f"crud/phone- check_phone_code. Код не действителен(прошло больше 10 минут)")
        raise HTTPException(status_code=400, detail={
            "msg": "Код не действителен(прошло больше 10 минут)"
        })
    db_phone_call.phone_validate = True
    db.commit()
    return True


def verify_phone(db: Session, number: str, user: User):
    db_user = db.query(User).filter(User.id == user.id).one_or_none()
    db_user.phone = number
    db_user.phoneVerified = True
    db.commit()
