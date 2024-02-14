from app.core.config import settings


# def test_create_tables(create_test_tables):
#   # Создание таблиц в тестовой БД
#     pass


def test_get_version(test_client):
    """
    Тестируем версию приложения. Сравниваем версию из БД и .env
    :param test_client: httpx TestClient
    :param test_info_doc_data: Добавление записей в БД
    """
    response = test_client.get("api/v1/main/version")
    print(f"Request URL: {response.url}")
    assert response.status_code == 200
    assert response.json() == {"version": settings.VERSION}


def test_info_documents(test_client, test_info_doc_data):
    """
    Тестируем документацию. Добавляем запись в текстовую БД и проверяем на правильность.
    :param test_client: httpx TestClient
    :param test_info_doc_data: Добавление записей в БД
    """

    response = test_client.get("api/v1/main/terms")

    assert response.status_code == 200
    assert response.json() == {
        "is_anchor": False,
        "type": "terms",
        "title": "Terms of Use",
        "description": "Sample Terms of Use",
        "rules": [
            {"title": "Rule 1", "description": "Sample Rule 1"},
            {"title": "Rule 2", "description": "Sample Rule 2"}
        ]
    }


def test_autocomplete_search(test_client):
    """
    1. определяет параметр search_query.
    2. делает запрос к эндпоинту, используя test_client.
    3. Проверяет, что код состояния ответа равен 200.
    4. Проверяет, что содержимое ответа является словарем.
    5. Извлекает categories и autocomplete из ответа.
    6. Убеждается, что и categories, и autocomplete являются списками.
    7. Если categories не пуст, то для каждой категории проверяет, что она является словарем с ключами 'id' и 'filter'.
    :param test_client: httpx TestClient
    """
    # Define test data or parameters
    search_query = "транспорт"

    # Make the request to the endpoint
    response = test_client.get(f"/api/v1/main/autocomplete?search={search_query}")

    # Check if the response status code is 200 (OK)
    assert response.status_code == 200

    # Check if the response is a dictionary
    assert isinstance(response.json(), dict)

    # Extract categories and autocomplete from the response
    response_data = response.json()
    categories = response_data.get("categories")
    autocomplete = response_data.get("autocomplete")

    # Check if categories and autocomplete are lists
    assert isinstance(categories, list)
    assert isinstance(autocomplete, list)

    if categories:
        for category in categories:
            # Check if first_category has keys 'id' and 'filter'
            assert isinstance(category, dict)
            assert "id" in category
            assert "filter" in category
