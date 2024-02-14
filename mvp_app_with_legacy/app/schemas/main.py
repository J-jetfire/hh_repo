from typing import List
from uuid import UUID

from pydantic import BaseModel


class AppVersionData(BaseModel):
    version: str


class AutocompleteCategories(BaseModel):
    id: UUID
    filter: str


class AutocompleteData(BaseModel):
    categories: List[AutocompleteCategories]
    autocomplete: List[str]


class InfoDocumentsRulesOut(BaseModel):
    title: str
    description: str


class InfoDocumentsOut(BaseModel):
    is_anchor: bool
    type: str
    title: str
    description: str
    rules: List[InfoDocumentsRulesOut]




