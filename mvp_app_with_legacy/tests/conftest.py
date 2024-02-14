import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.db_models import Base
from app.db.session import engine, SessionLocal


@pytest.fixture()
def app():
    """
    Эта фикстура создает экземпляр FastAPI приложения.

    Yields:
        FastAPI: Экземпляр FastAPI приложения.
    """
    from app.main import app
    yield app


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """
    Эта фикстура создает тестовые таблицы в базе данных.

    Yields:
        None
    """
    print('settings_Mode', settings.MODE)
    assert settings.MODE == 'TEST'
    # Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # yield
    # Clean up tables after tests
    # Base.metadata.drop_all(bind=engine)


# Фикстура для создания тестовой сессии базы данных
@pytest.fixture
def test_db(app):
    """
    Эта фикстура создает тестовую сессию базы данных SQLAlchemy.

    Args:
        app (FastAPI): Экземпляр FastAPI приложения.

    Returns:
        Session: Тестовая сессия базы данных.
    """
    return SessionLocal()


@pytest.fixture
def test_client(app):
    """
    Эта фикстура создает тестового клиента для приложения.

    Args:
        app (FastAPI): Экземпляр FastAPI приложения.

    Yields:
        TestClient: Тестовый клиент для отправки запросов.
    """
    # base_url = "http://192.168.88.23/"
    # with TestClient(app, base_url=base_url) as client:
    with TestClient(app) as client:
        yield client
