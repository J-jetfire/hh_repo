from typing import List
from uuid import UUID

from src.models import CustomModel, Roles


class CompanyContacts(CustomModel):
    id: UUID
    phone: str
    person: str | None


class UserCompany(CustomModel):
    id: UUID
    name: str
    address: str | None
    opening_time: str | None
    closing_time: str | None
    only_weekdays: bool
    contacts: List[CompanyContacts] = []


class UserResponse(CustomModel):
    id: int
    username: str
    is_active: bool
    is_admin: bool
    is_customer: bool
    is_executor: bool
    role: Roles | None
    name: str | None
    phone: str | None
    customer_company: UserCompany | None


class CustomerUserResponse(CustomModel):
    id: int
    username: str
    password: str
    # is_active: bool
    # name: str | None
    # phone: str | None
    customer_company: UserCompany | None


class CustomerShortCompany(CustomModel):
    name: str
    address: str


class CustomersList(CustomModel):
    id: int
    customer_company: CustomerShortCompany | None


class ExecutorsList(CustomModel):
    id: int
    name: str | None
    phone: str | None
    username: str


class CustomersListPaginated(CustomModel):
    total: int
    items: List[CustomersList]


class ExecutorUserResponse(CustomModel):
    id: int
    username: str
    password: str
    is_active: bool
    name: str
    phone: str | None  # TODO: Check could it be None?


class ExecutorsListPaginated(CustomModel):
    total: int
    items: List[ExecutorsList]


class CreateExecutorInput(CustomModel):
    username: str
    password: str
    name: str
    phone: str


class CustomerContacts(CustomModel):
    phone: str
    person: str


class CreateCustomerInput(CustomModel):
    username: str
    password: str
    name: str
    address: str
    opening_time: str
    closing_time: str
    only_weekdays: bool
    contacts: List[CustomerContacts]


class EditUserCredentials(CustomModel):
    username: str = None
    password: str = None


class EditUserPersonalData(CustomModel):
    name: str = None
    phone: str = None


class EditCustomerCompany(CustomModel):
    name: str = None
    address: str = None
    opening_time: str = None
    closing_time: str = None
    only_weekdays: bool = None


class EditCustomerContacts(CustomModel):
    phone: str
    person: str
