# tests/test_auth/test_login.py
import datetime
import random

from app.db.db_models import UserDevices
from app.utils.security import create_phone_token, decode_access_token, decode_refresh_token, hash_password
from tests.test_users.conftest import cleanup_user_device, cleanup_user


def test_successful_login_and_cleanup(test_db, test_client, cleanup_user_device, cleanup_user):
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

    for username, password, device_data, expected_status, expected_msg in [
        ("01234567891011", "TestPassword123", device_data, 404, "Некорректные данные для входа"),
        (user_phone, "TestPassword12345", device_data, 404, "Некорректные данные для входа"),
        (user_phone, "TestPassword123", "", 404, "Непредвиденная ошибка, попробуйте позже"),
        (user_phone, "TestPassword123", {}, 404, "Некорректные данные для входа"),
    ]:
        login_data = {
            "username": username,
            "password": password,
            "device": device_data
        }

        response = test_client.post("api/v1/auth/login", data=login_data)
        assert_error_response(response, expected_status, expected_msg)
        user_device_id = test_db.query(UserDevices.id).filter(UserDevices.user_id == subject).one_or_none()
        if user_device_id is not None:
            print('user_device_id', user_device_id[0])
            cleanup_user_device(user_device_id[0])

        else:
            print('User device ID is None')

    cleanup_user(subject)


def assert_error_response(response, expected_status, expected_msg):
    assert response.status_code == expected_status
    msg = response.json()['detail']['msg']
    assert msg == expected_msg
