import random
from datetime import datetime
import pytest
from app.db.db_models import User, UserDevices, UserLocation, UserPhoto
from app.utils.security import hash_password


@pytest.fixture
def test_user():
    """
    Эта фикстура создает тестовую запись пользователя и возвращает ее.

    Returns:
        User: Тестовый пользователь.
    """
    phone = ''.join(random.choice('0123456789') for _ in range(11))

    user = User(
        email="test@example.com",
        emailVerified=True,
        phone=phone,
        phoneVerified=True,
        googleId=None,
        appleId=None,
        # password="testpassword",
        password=hash_password("testpassword"),
        name="Test User",
        rating=1,
        rating_sum=1,
        feedback_count=1,
        contact_requests=1,
        views=1,
        unread_messages=1,
        online=True,
        online_at=None,
        createdAt=datetime.now(),
        updatedAt=None,
        lastLoginAt=None,
        is_active=True,
        is_blocked=False
    )
    return user


@pytest.fixture
def test_user_device(test_user, test_db):
    """
    Эта фикстура создает тестовую запись устройства пользователя и связывает ее с тестовым пользователем.

    Args:
        test_user (User): Тестовый пользователь.

    Returns:
        UserDevices: Тестовое устройство пользователя.
    """
    test_db.add(test_user)
    test_db.commit()

    user_device = UserDevices(
        user_id=test_user.id,
        token="testtoken",
        os="testos",
        brand="testbrand",
        deviceId="testdeviceid",
        model="testmodel",
        manufacturer="testmanufacturer",
        fingerprint="testfingerprint",
        ip="testip",
        userAgent="testuseragent",
        uniqueId="testuniqueid"
    )
    return user_device


@pytest.fixture
def test_user_location(test_user, test_db):
    """
    Эта фикстура создает тестовую запись местоположения пользователя и связывает ее с тестовым пользователем.

    Args:
        test_user (User): Тестовый пользователь.

    Returns:
        UserLocation: Тестовое местоположение пользователя.
    """
    test_db.add(test_user)
    test_db.commit()

    user_location = UserLocation(
        user_id=test_user.id,
        address="test address",
        full_address="test full address",
        country="test country",
        lat="test lat",
        long="test long",
        region="test region",
        district="test district",
        city="test city",
        street="test street",
        house="test house"
    )
    return user_location


@pytest.fixture
def test_user_photo(test_user, test_db):
    """
    Эта фикстура создает тестовую запись фотографии пользователя и связывает ее с тестовым пользователем.

    Args:
        test_user (User): Тестовый пользователь.

    Returns:
        UserPhoto: Тестовая фотография пользователя.
    """
    test_db.add(test_user)
    test_db.commit()

    user_photo = UserPhoto(
        user_id=test_user.id,
        url="test_url"
    )
    return user_photo


@pytest.fixture
def cleanup_user(test_db):
    """
    Эта фикстура удаляет только созданного пользователя после завершения теста.

    Args:
        :param test_db: Тестовая сессия базы данных.
        :param user_id: Идентификатор пользователя, которого нужно удалить.
    """
    def _cleanup(user_id):
        test_db.query(User).filter(User.id == user_id).delete()
        test_db.commit()

    yield _cleanup


@pytest.fixture
def cleanup_user_device(test_db):
    """
    Эта фикстура удаляет все записи местоположения пользователя после завершения теста.

    Args:
        :param test_db: Тестовая сессия базы данных.
        :param cleanup_user: Эта фикстура удаляет всех пользователей после завершения теста.
    """
    def _cleanup(user_device_id):
        # user_device = test_db.query(UserDevices).filter(UserDevices.id == user_device_id).one_or_none()
        # print('!user_id', user_device.user_id)
        test_db.query(UserDevices).filter(UserDevices.id == user_device_id).delete()
        test_db.commit()
        # cleanup_user(user_id)

    yield _cleanup


@pytest.fixture
def cleanup_user_location(test_db, cleanup_user):
    """
    Эта фикстура удаляет все записи местоположения пользователя после завершения теста.

    Args:
        :param test_db: Тестовая сессия базы данных.
        :param cleanup_user: Эта фикстура удаляет всех пользователей после завершения теста.
    """
    def _cleanup(user_location_id):
        test_db.query(UserLocation).filter(UserLocation.id == user_location_id).delete()
        test_db.commit()

    yield _cleanup


@pytest.fixture
def cleanup_user_photo(test_db, cleanup_user):
    """
    Эта фикстура удаляет все записи фотографий пользователя после завершения теста.

    Args:
        test_db: Тестовая сессия базы данных.
        cleanup_user: Фикстура для удаления пользователя.
    """
    def _cleanup(user_photo_id):
        test_db.query(UserPhoto).filter(UserPhoto.id == user_photo_id).delete()
        test_db.commit()

    yield _cleanup