import datetime
import random
import time
from tests.test_users.conftest import cleanup_user_device, cleanup_user
from app.db.db_models import UserDevices
from app.utils.security import create_refresh_token, decode_access_token, create_access_token, decode_refresh_token, \
    create_phone_token


# TODO: ADD REGISTRATION AND AUTHENTICATION
def test_refresh_token(test_client, test_db, cleanup_user_device, cleanup_user):
    user_data = {
        "name": "Test User",
        "password": "TestPassword123",
        "agree": True
    }
    user_phone = ''.join(random.choice('0123456789') for _ in range(11))
    response = test_client.post("api/v1/auth/registration", json=user_data,
                                headers={"Authorization": f"Bearer {create_phone_token({'sub': user_phone})}"})
    assert response.status_code == 201

    device_data = '{ "os": "test_os", "brand": "test_brand", "model": "test_model", "deviceId": "test_device_id", "manufacturer": "test_manufacturer", "fingerprint": "test_fingerprint", "ip": "test_ip", "userAgent": "test_user_agent", "uniqueId": "test_unique_id"}'

    # Пытаемся авторизоваться с созданным пользователем
    login_data = {
        "username": user_phone,
        "password": "TestPassword123",
        "device": device_data
    }

    response = test_client.post("api/v1/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

    access_token = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]

    access_token_data = decode_access_token(access_token)
    refresh_token_data = decode_refresh_token(refresh_token)

    assert "sub" in access_token_data
    assert "exp" in access_token_data

    assert "sub" in refresh_token_data
    assert "exp" in refresh_token_data

    subject = access_token_data["sub"]
    expiration_time = access_token_data["exp"]

    subject_refresh = refresh_token_data["sub"]
    expiration_time_refresh = refresh_token_data["exp"]

    current_time = datetime.datetime.utcnow()
    expiration_time = datetime.datetime.fromtimestamp(expiration_time)
    expiration_time_refresh = datetime.datetime.fromtimestamp(expiration_time_refresh)

    assert expiration_time > current_time
    assert expiration_time_refresh > current_time

    assert subject.isdigit()
    assert subject_refresh.isdigit()
    time.sleep(1)
    response = test_client.get(f"api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

    new_access_token = response.json()["access_token"]
    new_refresh_token = response.json()["refresh_token"]

    new_access_token_data = decode_access_token(new_access_token)
    assert "sub" in new_access_token_data
    assert "device" in new_access_token_data

    new_refresh_token_data = decode_refresh_token(new_refresh_token)
    assert "sub" in new_refresh_token_data
    assert "device" in new_refresh_token_data

    assert new_access_token != access_token
    assert new_refresh_token != refresh_token

    subject = new_access_token_data["sub"]
    subject_device = new_access_token_data["device"]

    subject_refresh = new_refresh_token_data["sub"]
    subject_device_refresh = new_refresh_token_data["device"]

    assert subject_device == 'test_unique_id' # uniqueId from device
    assert subject_device_refresh == 'test_unique_id' # uniqueId from device

    assert subject.isdigit()
    assert subject_refresh.isdigit()

    response = test_client.get(f"api/v1/auth/refresh", headers={"Authorization": f"Bearer {new_refresh_token}"})
    assert response.status_code == 200
    user_device_id = test_db.query(UserDevices.id).filter(UserDevices.user_id == subject).one_or_none()
    if user_device_id is not None:
        cleanup_user_device(user_device_id[0])
    cleanup_user(subject)


def generate_tokens(user_phone, device_data):
    access_token = create_access_token({"sub": user_phone, "device": device_data})
    refresh_token = create_refresh_token({"sub": user_phone, "device": device_data})
    return access_token, refresh_token
