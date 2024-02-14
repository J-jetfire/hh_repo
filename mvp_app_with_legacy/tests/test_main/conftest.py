import pytest
from app.db.db_models import InfoDocuments, InfoDocumentsRules


# Фикстура для тестирования данных о документации
@pytest.fixture
def test_info_doc_data(test_db):
    """
    Эта фикстура создает тестовые данные для проверки обработки информации о документации.

    Args:
        test_db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Yields:
        InfoDocuments: Объект InfoDocuments с созданными данными.
    """
    try:
        doc_info = InfoDocuments(
            is_anchor=False,
            type='terms',
            title='Terms of Use',
            description='Sample Terms of Use'
        )

        rule1 = InfoDocumentsRules(title='Rule 1', description='Sample Rule 1')
        rule2 = InfoDocumentsRules(title='Rule 2', description='Sample Rule 2')

        doc_info.rules.append(rule1)
        doc_info.rules.append(rule2)

        test_db.add(doc_info)
        test_db.commit()
        test_db.refresh(doc_info)
        yield doc_info
        test_db.delete(doc_info)
        test_db.commit()
    finally:
        test_db.close()
