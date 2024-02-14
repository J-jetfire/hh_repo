import datetime
import random
from tests.test_users.conftest import cleanup_user_device, cleanup_user
from app.db.db_models import Ad, Catalog, User
from app.utils.security import decode_access_token, decode_refresh_token, create_phone_token, hash_password


# Тест создания объявления и удаления.
def test_ad_creation(test_ad, test_db, cleanup_ad, cleanup_catalog, cleanup_user):
    """
    Тест создания объявления.
    Сначала создаем объявление, проверяем и удаляем
    """

    # Сохраняем объявление в базе данных
    test_db.add(test_ad)
    test_db.commit()
    test_db.refresh(test_ad)
    # Проверяем, что объявление успешно сохранено в базе данных
    assert test_ad.id is not None

    cleanup_ad(test_ad.id)
    cleanup_catalog(test_ad.catalog_id)
    cleanup_user(test_ad.user_id)


def test_get_all_ads_by_filters(test_client):
    request_data = {
        "price_from": 10,
        "price_to": 500000,
        "sort": "date_desc",
        "page": 1,
        "limit": 10,
        "filters": {},
        "location": {},
        "radius": 10,
        "search": ""
    }

    response = test_client.post("/api/v1/items", json=request_data)

    assert response.status_code == 200
    assert "total" in response.json()
    assert "items" in response.json()
    assert isinstance(response.json()["total"], int)
    assert isinstance(response.json()["items"], list)

    for item in response.json()["items"]:
        assert isinstance(item["id"], str)
        assert isinstance(item["title"], str)
        assert isinstance(item["description"], str)
        assert isinstance(item["price"], str)
        assert isinstance(item["location"], dict)
        assert isinstance(item["photos"], (str, int))
        assert isinstance(item["favorite"], bool)
        assert isinstance(item["status"], str)
        assert isinstance(item["created_at"], str)


def test_get_all_ads(test_client):
    response = test_client.get("/api/v1/items")

    assert response.status_code == 200
    assert "total" in response.json()
    assert "items" in response.json()
    assert isinstance(response.json()["total"], int)
    assert isinstance(response.json()["items"], list)

    for item in response.json()["items"]:
        assert isinstance(item["id"], str)
        assert isinstance(item["title"], str)
        assert isinstance(item["description"], str)
        assert isinstance(item["price"], str)
        assert isinstance(item["location"], dict)
        assert isinstance(item["photos"], (str, int))
        assert isinstance(item["favorite"], bool)
        assert isinstance(item["status"], str)
        assert isinstance(item["created_at"], str)


def test_get_catalog_from_ad(test_client, test_ad, test_db, cleanup_ad, cleanup_catalog, cleanup_user):
    # Сохраняем объявление в базе данных
    test_db.add(test_ad)
    test_db.commit()

    # Проверяем, что объявление успешно сохранено в базе данных
    assert test_ad.id is not None

    # Assuming you have a valid UUID for testing
    ad_id = test_ad.id
    print('ad id:', ad_id)
    response = test_client.get(f"/api/v1/items/catalog/{ad_id}")
    print('response:', response.json())
    assert response.status_code == 200

    response_data = response.json()
    assert "ad_info" in response_data
    assert "catalog_info" in response_data

    ad_info = response_data["ad_info"]
    catalog_info = response_data["catalog_info"]

    # Check types and structure of ad_info
    assert isinstance(ad_info["id"], str)
    assert isinstance(ad_info["title"], str)
    assert isinstance(ad_info["description"], str)
    assert isinstance(ad_info["price"], int)
    assert isinstance(ad_info["location"], dict)
    assert isinstance(ad_info["communication"], dict)
    assert isinstance(ad_info["fields"], dict)
    assert isinstance(ad_info["photos"], list)

    # Check types and structure of catalog_info
    assert isinstance(catalog_info["id"], str)
    assert isinstance(catalog_info["parent_id"], str)
    assert isinstance(catalog_info["path"], dict)
    assert isinstance(catalog_info["title"], dict)
    assert isinstance(catalog_info["is_publish"], bool)
    assert isinstance(catalog_info["dynamic_title"], list)
    assert isinstance(catalog_info["additional_fields"], list)

    for field in catalog_info["additional_fields"]:
        assert isinstance(field["alias"], str)
        assert isinstance(field["title"], str)
        assert isinstance(field["required"], bool)
        assert isinstance(field["data"], dict)

    cleanup_ad(test_ad.id)
    cleanup_catalog(test_ad.catalog_id)
    cleanup_user(test_ad.user_id)


def test_get_user_ads_published(test_client, test_ad, test_db, cleanup_ad, cleanup_user_device, cleanup_catalog, cleanup_user):
    # Add a test ad to the database
    test_db.add(test_ad)
    test_db.commit()

    # Check if the ad was successfully saved in the database
    assert test_ad.id is not None

    device_data = '{ "os": "test_os", "brand": "test_brand", "model": "test_model", "deviceId": "test_device_id", "manufacturer": "test_manufacturer", "fingerprint": "test_fingerprint", "ip": "test_ip", "userAgent": "test_user_agent", "uniqueId": "test_unique_id"}'

    # Пытаемся авторизоваться с созданным пользователем
    login_data = {
        "username": test_ad.user.phone,
        "password": "testpassword",
        "device": device_data
    }
    # Log in the user
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

    headers = {"Authorization": f"Bearer {access_token}"}
    response = test_client.get("/api/v1/items/user/published", headers=headers)

    assert response.status_code == 200

    response_data = response.json()
    assert "total" in response_data
    assert "items" in response_data

    total_ads = response_data["total"]
    ad_items = response_data["items"]
    assert isinstance(total_ads, int)
    # Check the types and structure of ad items
    for item in ad_items:
        assert isinstance(item["id"], str)
        assert isinstance(item["title"], str)
        assert isinstance(item["description"], str)
        assert isinstance(item["price"], str)
        assert isinstance(item["location"], dict)
        assert isinstance(item["photos"], (str, int))
        assert isinstance(item["favorite"], bool)
        assert isinstance(item["status"], str)
        assert isinstance(item["created_at"], str)

    test_db.refresh(test_ad)
    user_device_id = test_ad.user.device[0].id

    # Clean up
    cleanup_ad(test_ad.id)
    cleanup_catalog(test_ad.catalog_id)
    cleanup_user_device(user_device_id)
    cleanup_user(subject)


def test_get_advertisement_by_id(test_client, test_ad, test_db, cleanup_ad, cleanup_user_device, cleanup_catalog, cleanup_user):
    # Add a test ad to the database
    test_db.add(test_ad)
    test_db.commit()

    # Check if the ad was successfully saved in the database
    assert test_ad.id is not None

    device_data = '{ "os": "test_os", "brand": "test_brand", "model": "test_model", "deviceId": "test_device_id", "manufacturer": "test_manufacturer", "fingerprint": "test_fingerprint", "ip": "test_ip", "userAgent": "test_user_agent", "uniqueId": "test_unique_id"}'

    # Log in the user
    login_data = {
        "username": test_ad.user.phone,
        "password": "testpassword",
        "device": device_data
    }
    response = test_client.post("api/v1/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

    access_token = response.json()["access_token"]

    access_token_data = decode_access_token(access_token)

    assert "sub" in access_token_data
    assert "exp" in access_token_data

    subject = access_token_data["sub"]
    expiration_time = access_token_data["exp"]

    current_time = datetime.datetime.utcnow()
    expiration_time = datetime.datetime.fromtimestamp(expiration_time)

    assert expiration_time > current_time
    assert subject.isdigit()

    headers = {"Authorization": f"Bearer {access_token}"}
    response = test_client.get(f"/api/v1/items/{test_ad.id}", headers=headers)

    assert response.status_code == 200

    response_data = response.json()
    assert "id" in response_data
    assert "title" in response_data
    assert "description" in response_data
    assert "price" in response_data
    assert "location" in response_data
    assert "communication" in response_data
    assert "fields" in response_data
    assert "photos" in response_data
    assert "favorite" in response_data
    assert "created_at" in response_data
    assert "views" in response_data
    assert "status" in response_data
    assert "owner" in response_data

    assert isinstance(response_data["id"], str)
    assert isinstance(response_data["title"], str)
    assert isinstance(response_data["description"], str)
    assert isinstance(response_data["price"], int)
    assert isinstance(response_data["location"], dict)
    assert isinstance(response_data["communication"], dict)
    assert isinstance(response_data["fields"], dict)
    assert isinstance(response_data["photos"], list)
    assert isinstance(response_data["favorite"], bool)
    assert isinstance(response_data["created_at"], str)
    assert isinstance(response_data["views"], int)
    assert isinstance(response_data["status"], str)

    owner_data = response_data["owner"]
    assert "id" in owner_data
    assert "name" in owner_data
    assert "photo" in owner_data
    assert "rating" in owner_data
    assert "phone" in owner_data
    assert "is_active" in owner_data
    assert "adv_count" in owner_data
    assert "adv" in owner_data

    assert isinstance(owner_data["id"], int)
    assert isinstance(owner_data["name"], str)
    assert isinstance(owner_data["photo"], (str, type(None)))
    assert isinstance(owner_data["rating"], (float, type(None)))
    assert isinstance(owner_data["phone"], (str, type(None)))
    assert isinstance(owner_data["is_active"], bool)
    assert isinstance(owner_data["adv_count"], (int, type(None)))
    assert isinstance(owner_data["adv"], list)

    # Clean up
    cleanup_ad(test_ad.id)
    cleanup_catalog(test_ad.catalog_id)
    cleanup_user_device(test_ad.user.device[0].id)
    cleanup_user(subject)


def test_get_minicard_advertisement(test_client, test_ad, test_db, cleanup_ad, cleanup_catalog, cleanup_user):
    # Сохраняем объявление в базе данных
    test_db.add(test_ad)
    test_db.commit()

    # Проверяем, что объявление успешно сохранено в базе данных
    assert test_ad.id is not None

    # Assuming you have a valid UUID for testing
    ad_id = test_ad.id
    response = test_client.get(f"/api/v1/items/{ad_id}/minicard")
    assert response.status_code == 200

    response_data = response.json()
    assert "id" in response_data
    assert "title" in response_data
    assert "description" in response_data
    assert "price" in response_data
    assert "location" in response_data
    assert "photos" in response_data
    assert "favorite" in response_data
    assert "status" in response_data
    assert "created_at" in response_data

    # Check types of the response data
    assert isinstance(response_data["id"], str)
    assert isinstance(response_data["title"], str)
    assert isinstance(response_data["description"], str)
    assert isinstance(response_data["price"], str)
    assert isinstance(response_data["location"], dict)
    assert isinstance(response_data["photos"], (str, int))
    assert isinstance(response_data["favorite"], bool)
    assert isinstance(response_data["status"], str)
    assert isinstance(response_data["created_at"], str)

    cleanup_ad(test_ad.id)
    cleanup_catalog(test_ad.catalog_id)
    cleanup_user(test_ad.user_id)

