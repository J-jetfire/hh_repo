from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload
from app.db.db_models import Catalog, AdditionalFields, DynamicTitle, ChoiceTypes
from app.logger import setup_logger
from app.schemas.catalog import CatalogSubCategory, CatalogSchema
logger = setup_logger(__name__)

# Рекурсивная функция для построения древовидной структуры каталога
def build_catalog_tree(catalog_items, parent_id=None):
    sub_categories = []

    for catalog_item in catalog_items:
        if catalog_item.parent_id == parent_id:
            sub_category = CatalogSubCategory(
                id=catalog_item.id,
                parent_id=catalog_item.parent_id,
                path=catalog_item.path[0].to_dict(),
                title=catalog_item.title[0].to_dict(),
                is_publish=catalog_item.is_publish
            )
            sub_category.sub_categories = build_catalog_tree(catalog_items, parent_id=catalog_item.id)
            sub_categories.append(sub_category)

    return sub_categories


# Функция построения каталога
def get_catalog(db: Session):
    # Получаем все каталоги с предварительной загрузкой связанных данных
    catalog_data = db.query(Catalog).options(
        selectinload(Catalog.path),
        selectinload(Catalog.title)
    ).all()

    if not catalog_data:
        logger.error(f"crud/catalog- get_catalog. Каталог не найден: no catalog_data")
        raise HTTPException(status_code=404, detail="Каталог не найден")

    catalog_tree = []

    for catalog_item in catalog_data:
        if catalog_item.parent_id is None:
            catalog_schema = CatalogSchema(
                id=catalog_item.id,
                path=catalog_item.path[0].to_dict(),
                title=catalog_item.title[0].to_dict(),
                is_publish=catalog_item.is_publish
            )
            catalog_schema.sub_categories = build_catalog_tree(catalog_data, parent_id=catalog_item.id)
            catalog_tree.append(catalog_schema)

    if not catalog_tree:
        logger.error(f"crud/catalog- get_catalog. Каталог не найден: no catalog_tree")
        raise HTTPException(status_code=404, detail="Каталог не найден")

    return catalog_tree


# Функция получения доп. полей для элемента каталога
def get_all_fields(key, db: Session):
    query = db.query(Catalog).options(
        selectinload(Catalog.additional_fields),
        selectinload(Catalog.dynamic_title)
    )
    if key:
        query = query.filter(Catalog.id == key)
    catalogs = query.all()
    if not catalogs:
        logger.error(f"crud/catalog- get_all_fields. Ошибка получения доп.полей")
        raise HTTPException(status_code=404, detail="Ошибка получения доп.полей")

    # Формируем каталог и соответствующие доп.поля
    result = []
    for catalog in catalogs:
        additional_fields = []

        for field in catalog.additional_fields:
            field_data_dict = {}

            for field_data in field.field_data:
                properties = {}
                dependencies_data = []

                if field_data.type == ChoiceTypes.SELECT:
                    properties = { "options": field_data.properties }
                elif field_data.type == ChoiceTypes.TEXT:
                    properties = { "measure": field_data.properties[0] }
                elif field_data.type == ChoiceTypes.CHECKBOXES:
                    properties = { "checks": field_data.properties }
                elif field_data.type == ChoiceTypes.NUMBER:
                    properties = {
                        "measure": field_data.properties.measure,
                        "type": field_data.properties.type,
                        "min": field_data.properties.min,
                        "max": field_data.properties.max
                    }
                elif field_data.type == ChoiceTypes.REQUEST:
                    properties = {
                        "url": field_data.properties.url,
                        "dependencies": dependencies_data
                    }
                    if field_data.properties.dependencies:
                        dependencies_data.extend(
                            dependency.dependency
                            for dependency in field_data.properties.dependencies
                        )

                elif field_data.type == ChoiceTypes.COLOR:
                    properties = { "colors": field_data.properties }

                dependencies = [dependency.dependency for dependency in field_data.dependencies]

                field_data_dict = {
                    "type": field_data.type.value,
                    "edit": field_data.edit,
                    "show_filter": field_data.show_filter,
                    "range": field_data.range,
                    "dependencies": dependencies,
                    "properties": properties
                }

            additional_fields.append({
                "alias": field.alias,
                "title": field.title,
                "required": field.required,
                "data": field_data_dict
            })

        dynamic_title = [title.title for title in catalog.dynamic_title] if catalog.dynamic_title else []

        result.append({
            "id": str(catalog.id),
            "parent_id": str(catalog.parent_id),
            "path": catalog.path[0].to_dict(),
            "title": catalog.title[0].to_dict(),
            "is_publish": catalog.is_publish,
            "dynamic_title": dynamic_title,
            "additional_fields": additional_fields
        })
    # Возвращаем одну запись если получени идентификатор каталога, иначе выводим все записи
    return result[0] if key else result

