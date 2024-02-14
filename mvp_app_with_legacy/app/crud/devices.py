from sqlalchemy.orm import Session

from app.db.db_models import UserDevices
from app.schemas import user as user_schemas


def get_user_devices(user: user_schemas.UserOut, db: Session):
    db_devices = db.query(UserDevices).filter(
        UserDevices.user_id == user.id).all()
    return db_devices


def create_user_device(
        user: user_schemas.UserOut,
        device: user_schemas.UserDevicesCreate,
        token: str,
        db: Session
):
    db_device = db.query(UserDevices).where(
        UserDevices.uniqueId == device.uniqueId,
        UserDevices.user_id == user.id).one_or_none()
    if db_device:
        db.delete(db_device)
        db.commit()

    db_device = UserDevices(**device.dict(),
                            user_id=user.id,
                            token=token)
    db.add(db_device)
    db.commit()
    return True


def update_refresh_token(
        refresh_token_old: str,
        refresh_token_new: str,
        db: Session
):
    db_devices = db.query(UserDevices).filter(
        UserDevices.token == refresh_token_old).one_or_none()
    db_devices.token = refresh_token_new
    db.commit()
    return True


def delete_user_device(
        user: user_schemas.UserOut,
        uniqueId: str,
        db: Session
):
    db_device = db.query(UserDevices).where(
        UserDevices.uniqueId == uniqueId,
        UserDevices.user_id == user.id).delete()
    db.commit()
    return db_device


def delete_user_devices_except_current(
        refresh_token: str,
        user: user_schemas.UserOut,
        db: Session
):
    db_devices = db.query(UserDevices).filter(
        UserDevices.user_id == user.id).all()
    for device in db_devices:
        if device.token != refresh_token:
            db.delete(device)
    db.commit()
    return True


def delete_user_devices(user: user_schemas.UserOut, db: Session):
    db_devices = db.query(UserDevices).where(
        UserDevices.user_id == user.id).delete()
    db.commit()
    return db_devices
