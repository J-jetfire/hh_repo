import pytest
from tests.test_users.conftest import test_user, cleanup_user
from app.db.db_models import Ad, AdStatus, Catalog, MainCatalogTitle, MainCatalogPath


@pytest.fixture
def test_catalog(test_db):
    """
    Эта фикстура создает тестовую запись каталога.

    Args:
        test_db: Тестовая сессия базы данных.

    Returns:
        Catalog: Тестовый каталог.
    """
    catalog = Catalog(
        parent_id=None,
        is_publish=True
    )

    # Associate the MainCatalogPath and MainCatalogTitle with the Catalog
    # catalog.path = main_catalog_path
    # catalog.title = main_catalog_title

    # Add records to the database session
    test_db.add(catalog)
    test_db.commit()
    # Create a MainCatalogPath
    main_catalog_path = MainCatalogPath(
        parent_id=catalog.id,
        view="Test View",
        publish="Test Publish"
    )

    # Create a MainCatalogTitle
    main_catalog_title = MainCatalogTitle(
        parent_id=catalog.id,
        view="Test View",
        publish="Test Publish",
        view_translit="Test View Translit",
        publish_translit="Test Publish Translit",
        filter="Test Filter",
        price="123"
    )
    test_db.add(main_catalog_path)
    test_db.add(main_catalog_title)
    test_db.commit()

    return catalog


@pytest.fixture
def test_ad(test_user, test_catalog, test_db):
    """
    Эта фикстура создает тестовую запись объявления.

    Args:
        test_user (User): Тестовый пользователь.
        test_catalog (Catalog): Тестовая категория.
        test_status (AdStatus): Тестовый статус объявления.
        test_db: Тестовая сессия базы данных.

    Returns:
        Ad: Тестовое объявление.
    """
    test_db.add(test_user)
    test_db.commit()

    # try to find status = 3 or create
    status_with_id_3 = test_db.query(AdStatus).get(3)
    if not status_with_id_3:
        status_with_id_3 = AdStatus(
            status="publish",
            id=3
        )
        test_db.add(status_with_id_3)

    ad = Ad(
        user_id=test_user.id,
        catalog_id=test_catalog.id,
        status_id=status_with_id_3.id, # 3 => publish
        title="Test Ad",
        description="Test Description",
        price=1000,
        contact_by_phone=True,
        contact_by_message=True
    )
    return ad


@pytest.fixture
def cleanup_ad(test_db):
    """
    Эта фикстура удаляет все записи объявлений после завершения теста.

    Args:
        :param cleanup_user: Очистка записи пользователя
        :param cleanup_catalog: Очистка записи каталога
        :param test_db: Тестовая сессия базы данных.
        # :param cleanup_status: Очистка записи статуса объявления
    """
    def _cleanup(adv_id):
        test_db.query(Ad).filter(Ad.id == adv_id).delete()
        test_db.commit()

    yield _cleanup


@pytest.fixture
def cleanup_catalog(test_db):
    """
    Эта фикстура удаляет все записи объявлений после завершения теста.

    Args:
        test_db: Тестовая сессия базы данных.
    """
    def _cleanup(catalog_id):
        test_db.query(MainCatalogPath).filter(MainCatalogPath.parent_id == catalog_id).delete()
        test_db.query(MainCatalogTitle).filter(MainCatalogTitle.parent_id == catalog_id).delete()
        test_db.query(Catalog).filter(Catalog.id == catalog_id).delete()
        # test_catalog
        test_db.commit()

    yield _cleanup
