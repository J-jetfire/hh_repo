from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.auth import service as auth_service
from src.auth.exceptions import UsernameTaken, AuthorizationFailed
from src.auth.jwt import parse_jwt_user_data, validate_admin_access, validate_customer_access, validate_users_access
from src.auth.schemas import JWTData
from src.database import get_async_session
from src.models import User
from src.users import service as users_service
from src.users.schemas import (
    CreateCustomerInput,
    CreateExecutorInput,
    CustomersListPaginated,
    CustomerUserResponse,
    EditCustomerCompany,
    EditUserCredentials,
    EditUserPersonalData,
    ExecutorsListPaginated,
    ExecutorUserResponse,
    UserResponse, EditCustomerContacts, CompanyContacts,
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_my_account(
        jwt_data: JWTData = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    user = await users_service.get_user_profile_by_id(jwt_data.user_id, session)

    return user


@router.get("/customer/{user_id}", response_model=CustomerUserResponse, dependencies=[Depends(validate_admin_access)])
async def get_customer_account(
        user_id: int,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    role = "is_customer"
    user = await users_service.get_user_by_role(user_id, role, session)

    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="Пользователь на найден")


@router.get("/executor/{user_id}", response_model=ExecutorUserResponse, dependencies=[Depends(validate_admin_access)])
async def get_executor_account(
        user_id: int,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    role = "is_executor"
    user = await users_service.get_user_by_role(user_id, role, session)

    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="Пользователь на найден")


@router.get("/customers/all", response_model=CustomersListPaginated, dependencies=[Depends(validate_admin_access)])
async def get_customers_list(
        search: str = Query(None),
        page: int = 1,
        limit: int = Query(default=25, lte=50),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    offset = (page - 1) * limit
    response = await users_service.get_customers(search, offset, limit, session)

    return response


@router.get("/executors/all", response_model=ExecutorsListPaginated, dependencies=[Depends(validate_admin_access)])
async def get_executors_list(
        search: str = Query(None),
        page: int = 1,
        limit: int = Query(default=25, lte=50),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    offset = (page - 1) * limit
    response = await users_service.get_executors(search, offset, limit, session)

    return response


@router.post("/customers/create", status_code=status.HTTP_201_CREATED, response_model=CustomerUserResponse,
             dependencies=[Depends(validate_admin_access)])
async def create_new_customer(
        customer_data: CreateCustomerInput,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:

    user = await auth_service.get_user_by_username(customer_data.username, session)
    if user:
        raise UsernameTaken()

    customer = await users_service.create_customer(customer_data, session)

    if customer:
        role = "is_customer"
        user = await users_service.get_user_by_role(customer.id, role, session)
        if user:
            return user
        else:
            raise HTTPException(status_code=400, detail="Ошибка создания Заказчика")


@router.post("/executors/create", status_code=status.HTTP_201_CREATED, response_model=ExecutorUserResponse,
             dependencies=[Depends(validate_admin_access)])
async def create_new_executor(
        executor_data: CreateExecutorInput,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    user = await auth_service.get_user_by_username(executor_data.username, session)
    print(user)
    if user:
        raise UsernameTaken()

    executor = await users_service.create_executor(executor_data, session)

    if executor:
        return executor
    else:
        raise HTTPException(status_code=400, detail="Ошибка создания Исполнителя")


@router.delete("/block/{user_id}", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(validate_admin_access)])
async def block_user_account(
        user_id: int,
        session: AsyncSession = Depends(get_async_session)
) -> JSONResponse:
    result = await users_service.block_user(user_id, session)
    if result:
        return JSONResponse(content={"message": "Пользователь успешно удален(заблокирован)"})
    else:
        raise HTTPException(status_code=404, detail="Пользователь не найден")


@router.patch("/credentials/{user_id}", response_model=UserResponse, dependencies=[Depends(validate_admin_access)])
async def edit_users_credentials_by_admin(
        user_id: int,
        user_data: EditUserCredentials,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    if user_data.username:
        user = await auth_service.get_user_by_username(user_data.username, session)
        if user:
            raise UsernameTaken()

    user = await users_service.edit_credentials(user_id, user_data, session)

    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="Пользователь на найден")


@router.patch("/personal_data/{user_id}", response_model=UserResponse, dependencies=[Depends(validate_admin_access)])
async def edit_users_personal_data_by_admin(
        user_id: int,
        user_data: EditUserPersonalData,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    user = await users_service.edit_personal_data(user_id, user_data, session)

    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="Пользователь на найден")


@router.patch("/me/credentials", response_model=UserResponse)
async def edit_my_credentials(
        user_data: EditUserCredentials,
        jwt_data: JWTData = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    if user_data.username:
        user = await auth_service.get_user_by_username(user_data.username, session)
        if user:
            raise UsernameTaken()

    user = await users_service.edit_credentials(jwt_data.user_id, user_data, session)

    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="Пользователь на найден")


@router.patch("/me/personal_data", response_model=UserResponse)
async def edit_my_personal_data(
        user_data: EditUserPersonalData,
        jwt_data: JWTData = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    user = await users_service.edit_personal_data(jwt_data.user_id, user_data, session)

    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="Пользователь на найден")


@router.patch("/company/{user_id}", response_model=CustomerUserResponse, dependencies=[Depends(validate_admin_access)])
async def edit_company_data(
        user_id: int,
        company_data: EditCustomerCompany,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    """
    Изменение данных компании заказчика по идентификатору пользователя

    Параметры:
    - user_id: Идентификатор пользователя (заказчика)
    - company_data: EditCustomerCompany -> Измененные данные компании
    - validate_admin_access: аутентификация администратора -> access_token

    Возвращает:
    - CustomerUserResponse: Модель заказчика
    """
    if company_data:
        role = "is_customer"
        user = await users_service.get_user_by_role(user_id, role, session)
        if user.customer_company:
            company_id = user.customer_company.id
            company = await users_service.edit_users_company(company_id, company_data, session)

            if company:
                user.customer_company = company
                return user
            else:
                raise HTTPException(status_code=400, detail="Ошибка при формировании ответа")
        raise HTTPException(status_code=404, detail="Компания не найдена")


@router.post("/contacts/create", status_code=status.HTTP_201_CREATED, response_model=CompanyContacts,
             dependencies=[Depends(validate_customer_access)])
async def create_company_contact_by_customer(
        contact_data: EditCustomerContacts,
        session: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(parse_jwt_user_data)
) -> dict[str, Any]:

    customer_id = int(current_user.user_id)
    contact = await users_service.create_new_contact(customer_id, contact_data, session)

    if not contact:
        raise HTTPException(status_code=400, detail="Ошибка создания контактных данных")

    return contact


@router.post("/contacts/create/{customer_id}", status_code=status.HTTP_201_CREATED, response_model=CompanyContacts,
             dependencies=[Depends(validate_admin_access)])
async def create_company_contact_by_admin(
        customer_id: int,
        contact_data: EditCustomerContacts,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:

    contact = await users_service.create_new_contact(customer_id, contact_data, session)

    if not contact:
        raise HTTPException(status_code=400, detail="Ошибка создания контактных данных")

    return contact


@router.delete("/contacts/delete/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_contacts(
        contact_id: UUID,
        session: AsyncSession = Depends(get_async_session),
        current_user: JWTData = Depends(parse_jwt_user_data)
) -> None:

    if not any([current_user.is_admin, current_user.is_customer]):
        raise AuthorizationFailed()

    customer_id = int(current_user.user_id) if current_user.is_customer else None
    await users_service.delete_customer_contact(contact_id, session, customer_id)


@router.patch("/contacts/edit/{contact_id}", status_code=status.HTTP_202_ACCEPTED)
async def edit_company_contacts(
        contact_id: UUID,
        contact_data: EditCustomerContacts,
        session: AsyncSession = Depends(get_async_session),
        current_user: JWTData = Depends(parse_jwt_user_data)
) -> None:

    if not any([current_user.is_admin, current_user.is_customer]):
        raise AuthorizationFailed()

    customer_id = int(current_user.user_id) if current_user.is_customer else None
    response = await users_service.edit_customer_contact(contact_id, contact_data, session, customer_id)
    return response
