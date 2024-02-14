import time


def test_user_creation(test_user, test_db, cleanup_user):
    """
    Пример теста создания пользователя.
    """
    # Сохраняем пользователя в базу данных
    test_db.add(test_user)
    test_db.commit()

    # Проверяем, что пользователь успешно сохранен в базе данных
    assert test_user.id is not None
    cleanup_user(test_user.id)


def test_user_device_creation(test_user_device, test_db, cleanup_user_device, cleanup_user):
    """
    Пример теста создания устройства пользователя.
    """

    # Сохраняем устройство пользователя в базе данных
    test_db.add(test_user_device)
    test_db.commit()

    # Проверяем, что устройство пользователя успешно сохранено в базе данных
    assert test_user_device.id is not None
    assert test_user_device.user_id is not None

    cleanup_user_device(test_user_device.id)
    cleanup_user(test_user_device.user_id)


def test_user_location_creation(test_user_location, test_db, cleanup_user_location, cleanup_user):
    """
    Пример теста создания местоположения пользователя.
    """

    # Сохраняем местоположение пользователя в базе данных
    test_db.add(test_user_location)
    test_db.commit()

    # Проверяем, что местоположение пользователя успешно сохранено в базе данных
    assert test_user_location.id is not None
    cleanup_user_location(test_user_location.id)
    cleanup_user(test_user_location.user_id)


def test_user_photo_creation(test_user_photo, test_db, cleanup_user_photo, cleanup_user):
    """
    Пример теста создания фотографии пользователя.
    """

    # Сохраняем фотографию пользователя в базе данных
    test_db.add(test_user_photo)
    test_db.commit()

    # Проверяем, что фотография пользователя успешно сохранена в базе данных
    assert test_user_photo.id is not None
    cleanup_user_photo(test_user_photo.id)
    cleanup_user(test_user_photo.user_id)
