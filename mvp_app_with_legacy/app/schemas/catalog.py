from uuid import UUID
from typing import List, Dict, Union
from pydantic import BaseModel


class CatalogSubCategory(BaseModel):
    id: UUID
    path: dict
    title: dict
    is_publish: bool
    sub_categories: List['CatalogSubCategory'] = []


class FieldData(BaseModel):
    type: str
    edit: bool
    show_filter: bool
    range: bool
    dependencies: List[str]
    properties: Union[List, Dict]


class AdditionalFields(BaseModel):
    alias: str
    title: str
    required: bool
    data: FieldData


class CatalogPath(BaseModel):
    view: str
    publish: str


class CatalogTitle(BaseModel):
    view: str
    publish: str
    view_translit: str
    publish_translit: str
    filter: str
    price: str


class CatalogSchemaAdditionalFields(BaseModel):
    id: UUID
    parent_id: Union[UUID, str]
    path: CatalogPath
    title: CatalogTitle
    is_publish: bool
    dynamic_title: List[str]
    additional_fields: List[AdditionalFields]


class CatalogSchema(BaseModel):
    id: UUID
    path: CatalogPath
    title: CatalogTitle
    is_publish: bool
    sub_categories: List[CatalogSubCategory] = []

    class Config:
        orm_mode = True


# NOT USED SCHEMAS
# class FieldTypeSelect(BaseModel):
#     options: List[str]
# class FieldTypeText(BaseModel):
#     measure: str
# class FieldTypeCheckboxes(BaseModel):
#     checks: str
# class FieldTypeNumber(BaseModel):
#     measure: str
#     type: str
#     min: int
#     max: int
# class FieldTypeRequest(BaseModel):
#     url: str
#     dependencies: List[str]
# class FieldTypeColor(BaseModel):
#     color_id: int
#     name: str
#     value: str
# class OptionColor(BaseModel):
#     colors: FieldTypeColor
# class DynamicTitle(BaseModel):
#     title: str
# class FieldDataDependencies(BaseModel):
#     dependency: str
# class FieldDataPropertiesOptions(BaseModel):
#     color_id: int
#     name: str
#     value: str
# class FieldDataProperties(BaseModel):
#     options: List[Union[FieldDataPropertiesOptions, str]]
