import datetime
import json
from typing import Any, List
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update, func, and_, desc, exists, case, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased

from src.models import Service, ServiceStatus, User, Company, OwnerTypes, MediaFiles, Roles
from src.services.schemas import ServiceCreateInput, ServiceCreateByAdminInput
from src.users.service import get_user_profile_by_id, get_user_by_role
from src.services import utils as service_utils


async def create_new_service_by_admin(
        customer_id: int,
        service_data: ServiceCreateByAdminInput,
        video_file: UploadFile,
        image_files: List[UploadFile],
        session: AsyncSession
) -> dict[str, Any] | None:

    try:
        if customer_id == service_data.executor_id:
            raise ValueError("Вы не можете назначить исполнение заявки заказчику")

        customer = await get_user_profile_by_id(customer_id, session)

        new_service = Service(
            customer_id=customer_id,
            executor_id=service_data.executor_id,
            company_id=customer.customer_company.id,
            title=service_data.title,
            description=service_data.description,
            material_availability=service_data.material_availability,
            emergency=service_data.emergency,
            custom_position=service_data.custom_position,
            viewed_admin=True,
            deadline_at=service_data.deadline_at,
            comment=service_data.comment,
            status=ServiceStatus.NEW
        )

        session.add(new_service)
        await session.commit()
        await session.refresh(new_service)

        new_service.customer = customer

        if service_data.executor_id:
            executor = await get_user_by_role(service_data.executor_id, "is_executor", session)
            new_service.executor = executor

        owner_type = OwnerTypes.CUSTOMER

        if video_file:
            uploaded_video = await service_utils.save_video(video_file=video_file, service_id=new_service.id, owner_type=owner_type)
            if not uploaded_video:
                raise ValueError("Ошибка загрузки видео")

        if image_files:
            uploaded_image = await service_utils.save_images(image_files=image_files, service_id=new_service.id, owner_type=owner_type)
            if not uploaded_image:
                raise ValueError("Ошибка загрузки фото")

        media_files = await get_media_files_by_service_id(new_service.id, session)
        new_service.media_files = media_files

        return new_service

    except Exception as e:
        # Обработка ошибок
        print(f"Error creating service by admin: {e}")
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # закрыть сессию после выполнения операций
        await session.close()


async def create_new_service_by_customer(
        customer_id: int,
        service_data: ServiceCreateInput,
        video_file: UploadFile,
        image_files: List[UploadFile],
        session: AsyncSession
) -> dict[str, Any] | None:
    try:
        customer = await get_user_profile_by_id(customer_id, session)

        new_service = Service(
            customer_id=customer_id,
            company_id=customer.customer_company.id,
            title=service_data.title,
            description=service_data.description,
            material_availability=service_data.material_availability,
            emergency=service_data.emergency,
            viewed_customer=True,
            deadline_at=service_data.deadline_at,
            status=ServiceStatus.NEW
        )

        session.add(new_service)
        await session.commit()
        await session.refresh(new_service)

        new_service.customer = customer

        owner_type = OwnerTypes.CUSTOMER

        if video_file:
            uploaded_video = await service_utils.save_video(video_file=video_file, service_id=new_service.id,
                                                            owner_type=owner_type)
            if not uploaded_video:
                raise ValueError("Ошибка загрузки видео")

        if image_files:
            uploaded_image = await service_utils.save_images(image_files=image_files, service_id=new_service.id,
                                                             owner_type=owner_type)
            if not uploaded_image:
                raise ValueError("Ошибка загрузки фото")

        media_files = await get_media_files_by_service_id(new_service.id, session)
        new_service.media_files = media_files

        return new_service

    except Exception as e:
        # Обработка ошибок
        print(f"Error creating service by customer: {e}")
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка создания заявки")
    finally:
        # закрыть сессию после выполнения операций
        await session.close()


async def assign_executor_to_service(assign_data, session: AsyncSession):
    try:
        select_query = (select(Service)
                        .options(selectinload(Service.customer).selectinload(User.customer_company).selectinload(Company.contacts))
                        .options(selectinload(Service.executor))
                        .options(selectinload(Service.media_files))
                        .where(Service.id == assign_data.service_id)
                        )
        model = await session.execute(select_query)
        service = model.scalar_one_or_none()

        service.executor_id = assign_data.executor_id
        service.status = ServiceStatus.WORKING
        if not service.viewed_admin:
            service.viewed_admin = True
        service.viewed_customer = False
        service.deadline_at = assign_data.deadline_at
        await session.commit()
        await session.refresh(service)

        return service

    except Exception as e:
        # Обработка ошибок
        print(f"Error assigning service to executor: {e}")
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка назначения заявки")
    finally:
        # закрыть сессию после выполнения операций
        await session.close()


async def get_media_files_by_service_id(service_id: UUID, session: AsyncSession):
    select_query = (
        select(Service).where(Service.id == service_id)
        .options(selectinload(Service.media_files))
    )
    model = await session.execute(select_query)
    service = model.scalar_one_or_none()
    media_files = service.media_files
    return media_files


async def get_service_executor_id(service_id: UUID, session: AsyncSession):
    select_query = select(Service).where(Service.id == service_id)
    model = await session.execute(select_query)
    service = model.scalar_one_or_none()
    service_executor_id = service.executor_id
    service_status = service.status

    return service_executor_id, service_status


async def mark_service_verifying(service_id: UUID, session: AsyncSession):
    try:
        # Update the Service status to VERIFYING
        update_query = (
            update(Service)
            .where(Service.id == service_id)
            .values(
                status=ServiceStatus.VERIFYING,
                viewed_admin=False,
                viewed_customer=False,
                viewed_executor=True,
            )
        )
        await session.execute(update_query)

        # Commit the changes to the database
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


async def get_service_card_by_id(service_id: UUID, role: Roles, session: AsyncSession):
    select_query = (select(Service)
                    .options(
                    selectinload(Service.customer).selectinload(User.customer_company).selectinload(Company.contacts))
                    .options(selectinload(Service.executor))
                    .options(selectinload(Service.media_files))
                    .where(Service.id == service_id)
                    )
    model = await session.execute(select_query)
    service = model.scalar_one_or_none()

    if role == Roles.ADMIN:
        if not service.viewed_admin:
            service.viewed_admin = True
            await session.commit()
            await session.refresh(service)
    elif role == Roles.CUSTOMER:
        if not service.viewed_customer:
            service.viewed_customer = True
            await session.commit()
            await session.refresh(service)
    elif role == Roles.EXECUTOR:
        if not service.viewed_executor:
            service.viewed_executor = True
            await session.commit()
            await session.refresh(service)

    return service


async def make_service_closed(service_id: UUID, session: AsyncSession):
    try:
        select_query = (select(Service)
                        .options(selectinload(Service.customer).selectinload(User.customer_company).selectinload(Company.contacts))
                        .options(selectinload(Service.executor))
                        .options(selectinload(Service.media_files))
                        .where(Service.id == service_id)
                        )
        model = await session.execute(select_query)
        service = model.scalar_one_or_none()

        service.status = ServiceStatus.CLOSED
        if not service.viewed_admin:
            service.viewed_admin = True
        service.viewed_customer = False
        service.viewed_executor = False

        await session.commit()
        await session.refresh(service)

        return service

    except Exception as e:
        # Обработка ошибок
        print(f"Error assigning service to executor: {e}")
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка закрытия заявки")
    finally:
        # закрыть сессию после выполнения операций
        await session.close()


async def get_all_companies_with_services_info(page: int, limit: int, session: AsyncSession, executor_id: int = None):
    offset = (page - 1) * limit

    #######################################################################
    if executor_id:
        count_query = (
            select(func.count())
            .select_from(Company)
            .where(exists().where(
                and_(
                    Service.company_id == Company.id,
                    Service.executor_id == executor_id
                )
            ))
        )

        query = (
            select(
                Company,
                func.bool_or(Service.viewed_executor == False).label("marked"),
                func.sum(case((and_(Service.status == ServiceStatus.WORKING, Service.executor_id == executor_id), 1),
                              else_=0)).label("working"),
                func.sum(case((and_(Service.status == ServiceStatus.VERIFYING, Service.executor_id == executor_id), 1),
                              else_=0)).label("verifying"),
                func.sum(case((and_(Service.status == ServiceStatus.CLOSED, Service.executor_id == executor_id), 1),
                              else_=0)).label("closed"),
            )
            .join(Service)  # Внутреннее соединение, чтобы выбрать только компании с сервисами
            .where(and_(
                Service.executor_id == executor_id
            ))
            .options(selectinload(Company.services))
            .group_by(Company.id)  # Группируем по компании
            .order_by(desc(func.max(Service.updated_at)))  # Сортируем по дате обновления первого сервиса
            .offset(offset)
            .limit(limit)
        )

    else:
        count_query = (
            select(func.count())
            .select_from(Company)
            .where(exists().where(Service.company_id == Company.id))
        )

        query = (
            select(
                Company,
                func.bool_or(Service.viewed_admin == False).label("marked"),
                func.sum(case((Service.status == ServiceStatus.NEW, 1), else_=0)).label("new"),
                func.sum(case((Service.status == ServiceStatus.WORKING, 1), else_=0)).label("working"),
                func.sum(case((Service.status == ServiceStatus.VERIFYING, 1), else_=0)).label("verifying"),
                func.sum(case((Service.status == ServiceStatus.CLOSED, 1), else_=0)).label("closed"),
            )
            .join(Service)  # Внутреннее соединение, чтобы выбрать только компании с сервисами
            .options(selectinload(Company.services))
            .group_by(Company.id)  # Группируем по компании
            .order_by(desc(func.max(Service.updated_at)))  # Сортируем по дате обновления первого сервиса
            .offset(offset)
            .limit(limit)
        )

    #######################################################################
    total_records = await session.execute(count_query)
    total = total_records.scalar()

    # Выполняем запрос и Получаем все объекты Company из результата
    result = await session.execute(query)
    companies = result.all()

    response = []

    for company_with_mark in companies:
        company = company_with_mark[0]
        marked = company_with_mark.marked

        company_object = {
            "id": company.id,
            "name": company.name,
            "address": company.address,
            "badge": {
                "mark": marked,
                "counter": company.new_services_count_executor(executor_id) if executor_id else company.new_services_count
            },
            "tabs": {
                "new": 0 if executor_id else company_with_mark.new,
                "working": company_with_mark.working,
                "verifying": company_with_mark.verifying,
                "closed": company_with_mark.closed,
            }
        }
        response.append(company_object)

    # Close the session
    await session.close()
    return response, total


async def get_services_by_status(service_status: ServiceStatus, company_id: UUID, sort: str, page: int, limit: int, session: AsyncSession, executor_id: int = None):
    offset = (page - 1) * limit

    if executor_id:
        count_query = (
            select(func.count())
            .select_from(Service)
            .where(Service.company_id == company_id, Service.status == service_status, Service.executor_id == executor_id)
        )

        query = (
            select(Service)
            .where(Service.company_id == company_id, Service.status == service_status, Service.executor_id == executor_id)
            .order_by(
                asc(Service.updated_at) if sort == "date_asc" else desc(Service.updated_at)
            )  # Сортируем по дате
            .offset(offset)
            .limit(limit)
        )

    else:
        count_query = (
            select(func.count())
            .select_from(Service)
            .where(Service.company_id == company_id, Service.status == service_status)
        )

        query = (
            select(Service)
            .where(Service.company_id == company_id, Service.status == service_status)
            .order_by(
                asc(Service.updated_at) if sort == "date_asc" else desc(Service.updated_at)
            )  # Сортируем по дате
            .offset(offset)
            .limit(limit)
        )

    total_records = await session.execute(count_query)
    total = total_records.scalar()

    result = await session.execute(query)

    # Получаем все объекты Company из результата
    services = result.scalars().all()

    return services, total


async def get_executor_services_by_status(service_status: ServiceStatus, executor_id: int, sort: str, page: int, limit: int, session: AsyncSession):
    offset = (page - 1) * limit

    count_query = (
        select(func.count())
        .select_from(Service)
        .where(Service.executor_id == executor_id, Service.status == service_status)
    )
    total_records = await session.execute(count_query)
    total = total_records.scalar()

    query = (
        select(Service)
        .where(Service.executor_id == executor_id, Service.status == service_status)
        .order_by(
            asc(Service.updated_at) if sort == "date_asc" else desc(Service.updated_at)
        )  # Сортируем по дате
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)

    # Получаем все объекты Company из результата
    services = result.scalars().all()

    return services, total


async def get_company_id_by_customer(customer_id: int, session: AsyncSession):
    select_query = select(Company.id).where(Company.user_id == customer_id)
    model = await session.execute(select_query)
    company_id = model.scalar_one_or_none()
    print('company_id', company_id)
    return company_id


async def get_customer_services_by_status(service_status: ServiceStatus, company_id: UUID, sort: str, page: int, limit: int, session: AsyncSession, customer_id: int):
    offset = (page - 1) * limit

    count_query = (
        select(func.count())
        .select_from(Service)
        .where(Service.company_id == company_id, Service.status == service_status, Service.customer_id == customer_id)
    )

    unviewed_count_query = (
        select(func.count())
        .select_from(Service)
        .where(Service.company_id == company_id, Service.status == service_status, Service.customer_id == customer_id, Service.viewed_customer == False)
    )

    query = (
        select(Service)
        .where(Service.company_id == company_id, Service.status == service_status, Service.customer_id == customer_id)
        .order_by(
            asc(Service.updated_at) if sort == "date_asc" else desc(Service.updated_at)
        )  # Сортируем по дате
        .offset(offset)
        .limit(limit)
    )

    total_records = await session.execute(count_query)
    total = total_records.scalar()

    total_records_unviewed = await session.execute(unviewed_count_query)
    total_unviewed = total_records_unviewed.scalar()

    result = await session.execute(query)

    # Получаем все объекты Company из результата
    services = result.scalars().all()

    return services, total, total_unviewed


# async def upload_video_and_image(
#         service_id: uuid.UUID = Form(...),
#         video_file: UploadFile = File(None),
#         image_files: List[UploadFile] = File(None),
#         current_user: User = Depends(parse_jwt_user_data)
# ):
#     if not video_file and not image_files:
#         raise HTTPException(status_code=400, detail="You must upload at least one file")
#
#     count_images = len(image_files) if image_files else 0
#     count_videos = 1 if video_file else 0
#
#     # Проверка общего числа файлов
#     total_files = count_images + count_videos
#     if total_files > 3:
#         raise HTTPException(status_code=400, detail="Total files cannot exceed 3")
#
#     # Проверка на количество видео файлов
#     if video_file and count_images > 2:
#         raise HTTPException(status_code=400, detail="If there is a video, there can be at most 2 images")
#
#     # Проверка на количество фото файлов
#     if not video_file and count_images > 3:
#         raise HTTPException(status_code=400, detail="If there is no video, there can be at most 3 images")
#
#     owner_type = None
#     if current_user.is_admin or current_user.is_customer:
#         owner_type = OwnerTypes.CUSTOMER
#
#     if current_user.is_executor:
#         owner_type = OwnerTypes.EXECUTOR
#
#     print(owner_type)
#
#     if video_file:
#         # background_tasks.add_task(save_video, video_file=video_file, service_id=service_id, owner_type=owner_type)
#         await service_utils.save_video(video_file=video_file, service_id=service_id, owner_type=owner_type)
#
#     if image_files:
#         # background_tasks.add_task(service_utils.save_images, image_files=image_files, service_id=service_id, owner_type=owner_type)
#         await service_utils.save_images(image_files=image_files, service_id=service_id, owner_type=owner_type)
#
#     print("SUCCESS")
#     return True
