from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, delete, desc, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import Company, CompanyContacts, User, Roles
from src.users.schemas import CreateCustomerInput, CreateExecutorInput, EditUserCredentials, EditUserPersonalData, \
    EditCustomerCompany, EditCustomerContacts


async def get_user_profile_by_id(user_id: int, session: AsyncSession) -> dict[str, Any] | None:
    select_query = select(User).where(User.id == user_id).options(
        selectinload(User.customer_company).selectinload(Company.contacts))
    model = await session.execute(select_query)
    user = model.scalar_one_or_none()
    return user


async def get_user_by_role(user_id: int, role: str, session: AsyncSession) -> dict[str, Any] | None:
    select_query = select(User).where(User.id == user_id)

    if role == "is_customer":
        select_query = select_query.where(User.is_customer, User.is_active).options(
            selectinload(User.customer_company).selectinload(Company.contacts))
    elif role == "is_executor":
        select_query = select_query.where(User.is_executor, User.is_active)

    user = await session.execute(select_query)
    response = user.scalar_one_or_none()
    return response


async def get_customers(search: str, offset: int, limit: int, session: AsyncSession) -> dict[str, Any] | None:
    search_conditions = []

    if search:
        search_conditions.append(or_(
            Company.name.ilike(f"%{search}%"),
            Company.address.ilike(f"%{search}%")
        ))

    base_condition = User.is_customer

    if search_conditions:
        base_condition = and_(base_condition, *search_conditions)

    count_query = (
        select(func.count())
        .select_from(User)
        .join(Company, User.customer_company)
        .where(base_condition, User.is_active)
    )

    total_records = await session.execute(count_query)
    total = total_records.scalar()

    select_query = (
        select(User.id, Company.name, Company.address)
        .join(Company)
        .where(base_condition, User.is_active)
        .order_by(desc(User.created_at))
        .offset(offset)
        .limit(limit)
    )

    customers = await session.execute(select_query)
    response = customers.fetchall()

    response_data = []
    for user_id, company_name, company_address in response:
        response_data.append({
            "id": user_id,
            "customer_company": {
                "name": company_name,
                "address": company_address
            }
        })

    response = {
        "total": total,
        "items": response_data
    }
    return response


async def get_executors(search: str, offset: int, limit: int, session: AsyncSession) -> dict[str, Any] | None:
    search_conditions = []

    if search:
        search_conditions.append(or_(
            User.name.ilike(f"%{search}%"),
            User.phone.ilike(f"%{search}%")
        ))

    base_condition = User.is_executor == True

    if search_conditions:
        base_condition = and_(base_condition, *search_conditions)

    count_query = (
        select(func.count())
        .select_from(User)
        .where(base_condition, User.is_active)
    )

    total_records = await session.execute(count_query)
    total = total_records.scalar()

    select_query = (
        select(User.id, User.name, User.phone, User.username)
        .where(base_condition, User.is_active)
        .order_by(desc(User.created_at))
        .offset(offset)
        .limit(limit)
    )

    executors = await session.execute(select_query)
    response = executors.fetchall()

    response_data = []
    for user in response:
        response_data.append({
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
            "username": user.username
        })

    response = {
        "total": total,
        "items": response_data
    }
    return response


async def create_executor(executor_data: CreateExecutorInput, session: AsyncSession) -> dict[str, Any] | None:
    try:
        executor = User(
            username=executor_data.username,
            password=executor_data.password,
            is_active=True,
            is_executor=True,
            name=executor_data.name,
            phone=executor_data.phone,
            role=Roles.EXECUTOR
        )

        session.add(executor)
        await session.commit()
        await session.refresh(executor)

        return executor

    except Exception as e:
        # Обработка ошибок
        print(f"Error creating executor: {e}")
        await session.rollback()
        return None
    finally:
        # Не забудьте закрыть сессию после выполнения операций
        await session.close()


async def create_customer(customer_data: CreateCustomerInput, session: AsyncSession) -> dict[str, Any] | None:
    try:
        customer = User(
            username=customer_data.username,
            password=customer_data.password,
            is_active=True,
            is_customer=True,
            role=Roles.CUSTOMER
        )

        session.add(customer)
        await session.commit()
        await session.refresh(customer)

        customer_company = Company(
            user_id=customer.id,
            name=customer_data.name,
            address=customer_data.address,
            opening_time=customer_data.opening_time,
            closing_time=customer_data.closing_time,
            only_weekdays=customer_data.only_weekdays,
        )

        session.add(customer_company)
        await session.commit()
        await session.refresh(customer_company)

        for contact in customer_data.contacts:
            company_contact = CompanyContacts(
                company_id=customer_company.id,
                phone=contact.phone,
                person=contact.person,
            )
            session.add(company_contact)

        await session.commit()
        return customer

    except Exception as e:
        # Обработка ошибок
        print(f"Error creating customer: {e}")
        await session.rollback()
        return None
    finally:
        # Не забудьте закрыть сессию после выполнения операций
        await session.close()


async def block_user(user_id: int, session: AsyncSession) -> bool:
    select_query = select(User).where(User.id == user_id)
    model = await session.execute(select_query)
    user = model.scalar_one_or_none()

    if user:
        if user.is_active:
            user.is_active = False
            await session.commit()
            return True

    return False


async def edit_credentials(user_id: int, user_data: EditUserCredentials, session: AsyncSession) -> dict[str, Any] | None:
    user = await get_user_profile_by_id(user_id, session)

    if user:
        if user.is_active:
            if not user_data:
                return None

            if user_data.username:
                user.username = user_data.username
            if user_data.password:
                user.password = user_data.password

            await session.commit()
            await session.refresh(user)
            return user
    return None


async def edit_personal_data(
        user_id: int,
        user_data: EditUserPersonalData, session: AsyncSession
) -> dict[str, Any] | None:
    user = await get_user_profile_by_id(user_id, session)

    if user:
        if user.is_active:
            if not user_data:
                return None

            if user_data.name:
                user.name = user_data.name
            if user_data.phone:
                user.phone = user_data.phone

            await session.commit()
            await session.refresh(user)
            return user
    return None


async def get_company_by_id(company_id: UUID, session: AsyncSession):
    select_query = select(Company).where(Company.id == company_id).options(selectinload(Company.contacts))
    model = await session.execute(select_query)
    company = model.scalar_one_or_none()
    return company


async def edit_users_company(company_id: UUID, company_data: EditCustomerCompany, session: AsyncSession) -> dict[str, Any] | None:
    company = await get_company_by_id(company_id, session)

    if company:
        if company_data.name:
            company.name = company_data.name
        if company_data.address:
            company.address = company_data.address
        if company_data.opening_time:
            company.opening_time = company_data.opening_time
        if company_data.closing_time:
            company.closing_time = company_data.closing_time
        if company_data.only_weekdays:
            company.only_weekdays = company_data.only_weekdays

        await session.commit()
        await session.refresh(company)
        return company
    return None


async def create_new_contact(customer_id: int, contact_data, session: AsyncSession) -> dict[str, Any]:
    select_query = select(Company.id).where(Company.user_id == customer_id)
    model = await session.execute(select_query)
    company_id = model.scalar_one_or_none()

    contact = CompanyContacts(
        company_id=company_id,
        phone=contact_data.phone,
        person=contact_data.person
    )

    session.add(contact)
    await session.commit()
    await session.refresh(contact)

    return contact


async def delete_customer_contact(contact_id: UUID, session: AsyncSession, customer_id: int = None):
    if customer_id:
        delete_query = (
            delete(CompanyContacts)
            .where(CompanyContacts.id == contact_id)
            .where(CompanyContacts.company.has(Company.user_id == customer_id))
        )
    else:
        delete_query = delete(CompanyContacts).where(CompanyContacts.id == contact_id)

    try:
        result = await session.execute(delete_query)
        affected_rows = result.rowcount

        if affected_rows == 0:
            raise NoResultFound()

        await session.execute(delete_query)
        await session.commit()
        print('Contact deleted successfully')

    except Exception as e:
        print(f"Error deleting contact: {e}")
        await session.rollback()
        raise HTTPException(status_code=400, detail="Ошибка удаления контактных данных")

    finally:
        await session.close()


# Update customer contacts by owner or admin
async def edit_customer_contact(contact_id: UUID, contact_data: EditCustomerContacts, session: AsyncSession, customer_id: int = None):
    try:
        if customer_id:
            update_query = (
                update(CompanyContacts)
                .where(CompanyContacts.id == contact_id)
                .where(CompanyContacts.company.has(Company.user_id == customer_id))
                .values(
                    phone=contact_data.phone,
                    person=contact_data.person
                )
            )
            await session.execute(update_query)
            await session.commit()

            return True

        else:
            update_query = (
                update(CompanyContacts)
                .where(CompanyContacts.id == contact_id)
                .values(
                    phone=contact_data.phone,
                    person=contact_data.person
                )
            )
            await session.execute(update_query)
            await session.commit()

            return True

    except Exception as e:
        # Handle exceptions appropriately
        await session.rollback()
        print(f"Error marking service as verifying: {e}")
        return False

    finally:
        # Close the session
        await session.close()
