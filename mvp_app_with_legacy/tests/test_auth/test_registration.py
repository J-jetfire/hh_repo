# tests/test_auth/test_registration.py
import random

from app.db.db_models import User
from app.utils.security import create_phone_token
from tests.test_users.conftest import cleanup_user


# Тест регистрации нового пользователя и его удаление
def test_successful_registration(test_client, test_db, cleanup_user):
    user_data = {
        "name": "Test User",
        "password": "TestPassword123",
        "agree": True
    }

    user_phone = ''.join(random.choice('0123456789') for _ in range(11))
    response = test_client.post("api/v1/auth/registration", json=user_data,
                                headers={"Authorization": f"Bearer {create_phone_token({'sub': user_phone})}"})
    assert response.status_code == 201
    assert response.json() == {"msg": "success"}

    user_id = test_db.query(User).filter(User.phone == user_phone).one_or_none()
    user_id = user_id.id
    cleanup_user(user_id)


# Тест регистрации на невалидный пароль
def test_invalid_password(test_client):
    user_data = {
        "name": "Test User",
        "password": "weakpassword",  # Пароль не соответствует требованиям
        "agree": True
    }

    user_phone = ''.join(random.choice('0123456789') for _ in range(11))
    response = test_client.post("api/v1/auth/registration", json=user_data,
                                headers={"Authorization": f"Bearer {create_phone_token({'sub': user_phone})}"})

    assert response.status_code == 403
    assert response.json() == {'detail': {'msg': 'Ошибка валидации пароля'}}


# Тест регистрации на отметку о пользовательском соглашении
def test_false_agree_field(test_client):
    user_data = {
        "name": "Test User",
        "password": "TestPassword123",
        "agree": False
    }
    user_phone = ''.join(random.choice('0123456789') for _ in range(11))
    response = test_client.post("api/v1/auth/registration", json=user_data,
                                headers={"Authorization": f"Bearer {create_phone_token({'sub': user_phone})}"})
    assert response.status_code == 400
    assert response.json() == {'detail': {'msg': 'Подтвердите согласие'}}


# Тест регистрации на отсутствие отметки о польз. соглашении
def test_missing_agree_field(test_client):
    user_data = {
        "name": "Test User",
        "password": "TestPassword123"
        # missing agree field
    }
    user_phone = ''.join(random.choice('0123456789') for _ in range(11))
    response = test_client.post("api/v1/auth/registration", json=user_data,
                                headers={"Authorization": f"Bearer {create_phone_token({'sub': user_phone})}"})
    assert response.status_code == 422


# Тест регистрации на отсутствие токена номера телефона
def test_missing_user_phone_token(test_client):
    user_data = {
        "name": "Test User",
        "password": "TestPassword123",
        "agree": True
    }
    response = test_client.post("api/v1/auth/registration", json=user_data)
    assert response.status_code == 401