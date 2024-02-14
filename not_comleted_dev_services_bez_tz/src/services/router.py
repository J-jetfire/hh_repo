import uuid
from datetime import datetime
from typing import Any, List
import aiofiles
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.exceptions import AuthorizationFailed
from src.auth.jwt import validate_admin_access, validate_customer_access, parse_jwt_user_data
from src.database import get_async_session
from src.models import User, OwnerTypes, ServiceStatus, Roles
from src.services.schemas import ServiceResponse, ServiceCreateInput, ServiceCreateByAdminInput, ServiceAssignInput, \
    CompaniesListPaginated, ServicesListPaginated, CustomerServicesListPaginated
from src.services import service as services
from src.services import utils as service_utils

router = APIRouter()


@router.get("/get/{service_id}", response_model=ServiceResponse)
async def get_service_card(
        service_id: uuid.UUID,
        session: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(parse_jwt_user_data)
):
    service = await services.get_service_card_by_id(service_id, current_user.role, session)
    return service


@router.post("/create_by_admin", status_code=status.HTTP_201_CREATED, response_model=ServiceResponse,
             dependencies=[Depends(validate_admin_access)])
async def create_new_service_by_admin(
        customer_id: int = Form(...),
        executor_id: int = Form(None),
        title: str = Form(...),
        description: str = Form(None),
        material_availability: bool = Form(None),
        emergency: bool = Form(None),
        custom_position: bool = Form(None),
        deadline_at: datetime = Form(None),
        comment: str = Form(None),
        video_file: UploadFile = File(None),
        image_files: List[UploadFile] = File(None),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:

    # if not video_file and not image_files:
    #     raise HTTPException(status_code=400, detail="You must upload at least one file")

    count_images = len(image_files) if image_files else 0
    count_videos = 1 if video_file else 0

    # Проверка общего числа файлов
    total_files = count_images + count_videos
    if total_files > 3:
        raise HTTPException(status_code=400, detail="Total files cannot exceed 3")

    # Проверка на количество видео файлов
    if video_file and count_images > 2:
        raise HTTPException(status_code=400, detail="If there is a video, there can be at most 2 images")

    # Проверка на количество фото файлов
    if not video_file and count_images > 3:
        raise HTTPException(status_code=400, detail="If there is no video, there can be at most 3 images")

    service_data = ServiceCreateByAdminInput(
        customer_id=customer_id,
        executor_id=executor_id,
        title=title,
        description=description,
        material_availability=material_availability,
        emergency=emergency,
        custom_position=custom_position,
        deadline_at=deadline_at,
        comment=comment
    )

    new_service = await services.create_new_service_by_admin(service_data.customer_id, service_data, video_file, image_files, session)

    if not new_service:
        raise HTTPException(status_code=400, detail="Ошибка создания заявки")

    return new_service


@router.post("/create", status_code=status.HTTP_201_CREATED, response_model=ServiceResponse,
             dependencies=[Depends(validate_customer_access)])
async def create_new_service(
        title: str = Form(...),
        description: str = Form(None),
        material_availability: bool = Form(None),
        emergency: bool = Form(None),
        deadline_at: datetime = Form(None),
        video_file: UploadFile = File(None),
        image_files: List[UploadFile] = File(None),
        session: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(parse_jwt_user_data)
) -> dict[str, Any]:

    # if not video_file and not image_files:
    #     raise HTTPException(status_code=400, detail="You must upload at least one file")

    count_images = len(image_files) if image_files else 0
    count_videos = 1 if video_file else 0

    # Проверка общего числа файлов
    total_files = count_images + count_videos
    if total_files > 3:
        raise HTTPException(status_code=400, detail="Total files cannot exceed 3")

    # Проверка на количество видео файлов
    if video_file and count_images > 2:
        raise HTTPException(status_code=400, detail="If there is a video, there can be at most 2 images")

    # Проверка на количество фото файлов
    if not video_file and count_images > 3:
        raise HTTPException(status_code=400, detail="If there is no video, there can be at most 3 images")

    service_data = ServiceCreateInput(
        title=title,
        description=description,
        material_availability=material_availability,
        emergency=emergency,
        deadline_at=deadline_at
    )

    customer_id = int(current_user.user_id)
    new_service = await services.create_new_service_by_customer(customer_id, service_data, video_file, image_files, session)

    if not new_service:
        raise HTTPException(status_code=400, detail="Ошибка создания заявки")

    return new_service


@router.post("/assign", status_code=status.HTTP_200_OK, response_model=ServiceResponse,
             dependencies=[Depends(validate_admin_access)])
async def assign_executor(
        assign_data: ServiceAssignInput,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:

    attached_service = await services.assign_executor_to_service(assign_data, session)

    if not attached_service:
        raise HTTPException(status_code=400, detail="Ошибка назначения заявки")

    return attached_service


@router.post("/verify")
async def mark_service_verifying_by_executor(
        service_id: uuid.UUID = Form(...),
        video_file: UploadFile = File(None),
        image_files: List[UploadFile] = File(None),
        current_user: User = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
):

    if not any([current_user.is_admin, current_user.is_executor]):
        raise AuthorizationFailed()

    service_executor_id, service_status = await services.get_service_executor_id(service_id, session)

    if not service_executor_id:
        raise HTTPException(status_code=400, detail="У заявки должен быть назначен исполнитель")

    if not current_user.is_admin:
        if int(current_user.user_id) != int(service_executor_id):
            raise AuthorizationFailed()

    if service_status != ServiceStatus.WORKING:
        raise HTTPException(status_code=400, detail="Для отправления заявки на контроль качества, заявка должна иметь статус 'В работе'")

    if not video_file and not image_files:
        raise HTTPException(status_code=400, detail="You must upload at least one file")

    count_images = len(image_files) if image_files else 0
    count_videos = 1 if video_file else 0

    # Проверка общего числа файлов
    total_files = count_images + count_videos
    if total_files > 2:
        raise HTTPException(status_code=400, detail="Total files cannot exceed 2")

    # Проверка на количество видео файлов
    if video_file and count_images > 1:
        raise HTTPException(status_code=400, detail="If there is a video, there can be at most 1 image")

    # Проверка на количество фото файлов
    if not video_file and count_images > 2:
        raise HTTPException(status_code=400, detail="If there is no video, there can be at most 2 images")

    owner_type = OwnerTypes.EXECUTOR

    print(owner_type)

    if video_file:
        await service_utils.save_video(video_file=video_file, service_id=service_id, owner_type=owner_type)

    if image_files:
        await service_utils.save_images(image_files=image_files, service_id=service_id, owner_type=owner_type)

    marked_verifying = await services.mark_service_verifying(service_id, session)
    if not marked_verifying:
        raise HTTPException(status_code=400, detail="Ошибка отправления заявки на контроль качества")

    response = {
        "detail": "Заявка успешно отправлена на контроль качества"
    }
    return response


@router.post("/close/{service_id}", status_code=status.HTTP_200_OK, response_model=ServiceResponse, dependencies=[Depends(validate_admin_access)])
async def close_service(
        service_id: uuid.UUID,
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:

    closed_service = await services.make_service_closed(service_id, session)

    if not closed_service:
        raise HTTPException(status_code=400, detail="Ошибка закрытия заявки")

    return closed_service


@router.get("/companies/all", status_code=status.HTTP_200_OK, response_model=CompaniesListPaginated)
async def get_all_companies(
        page: int = 1,
        limit: int = Query(default=15, lte=50),
        current_user: User = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:

    if not any([current_user.is_admin, current_user.is_executor]):
        raise AuthorizationFailed()

    executor_id = int(current_user.user_id) if current_user.is_executor else None

    companies_list, total = await services.get_all_companies_with_services_info(page, limit, session, executor_id)

    response = {
        "total": total,
        "items": companies_list
    }

    return response


@router.get("/status/{value}/{company_id}", status_code=status.HTTP_200_OK, response_model=ServicesListPaginated)
async def get_all_company_services_by_status(
        company_id: uuid.UUID,
        value: str = Path(..., title="Status", description="Статус заявки", regex="^(new|working|verifying|closed)$"),
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=15, lte=50),
        current_user: User = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    """
    Получение списка заявок по статусу с пагинацией для администратора

    Параметры:
    - value: Статус заявки (new|working|verifying|closed).
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во заявок на одной странице.
    - session (AsyncSession): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - ServicesListPaginated: Общее кол-во заявок и список заявок на выбранной странице.
    """

    if not any([current_user.is_admin, current_user.is_executor]):
        raise AuthorizationFailed()

    executor_id = int(current_user.user_id) if current_user.is_executor else None

    status_mapping = {
        'new': ServiceStatus.NEW,
        'working': ServiceStatus.WORKING,
        'verifying': ServiceStatus.VERIFYING,
        'closed': ServiceStatus.CLOSED,
    }
    service_status = status_mapping.get(value, None)

    if service_status is None:
        raise HTTPException(status_code=400, detail="Статус не существует")

    services_list, total = await services.get_services_by_status(service_status, company_id, sort, page, limit, session, executor_id)

    response = {
        "total": total,
        "items": services_list
    }

    return response


# @router.get("/status/{value}", status_code=status.HTTP_200_OK, response_model=ServicesListPaginated)
@router.get("/customer/status/{value}", status_code=status.HTTP_200_OK, response_model=CustomerServicesListPaginated)
async def get_all_customer_services_by_status(
        value: str = Path(..., title="Status", description="Статус заявки", regex="^(new|working|verifying|closed)$"),
        sort: str = "date_desc",
        page: int = 1,
        limit: int = Query(default=15, lte=50),
        current_user: User = Depends(parse_jwt_user_data),
        session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    """
    Получение списка заявок по статусу с пагинацией для администратора

    Параметры:
    - value: Статус заявки (new|working|verifying|closed).
    - sort: Сортировка.
    - page: Страница.
    - limit: Кол-во заявок на одной странице.
    - session (AsyncSession): Сессия SQLAlchemy для взаимодействия с базой данных.

    Возвращает:
    - ServicesListPaginated: Общее кол-во заявок и список заявок на выбранной странице.
    """

    if not any([current_user.is_admin, current_user.is_customer]):
        raise AuthorizationFailed()

    customer_id = int(current_user.user_id) if current_user.is_customer else None

    status_mapping = {
        'new': ServiceStatus.NEW,
        'working': ServiceStatus.WORKING,
        'verifying': ServiceStatus.VERIFYING,
        'closed': ServiceStatus.CLOSED,
    }
    service_status = status_mapping.get(value, None)

    if service_status is None:
        raise HTTPException(status_code=400, detail="Статус не существует")

    company_id = await services.get_company_id_by_customer(customer_id, session)

    services_list, total, counter = await services.get_customer_services_by_status(service_status, company_id, sort, page, limit, session, customer_id)

    response = {
        "total": total,
        "counter": counter,
        "items": services_list
    }

    return response

# @router.get("/get_video")
# async def get_video():
#     file_path = "./static/name1.mp4"
#
#     async def stream_file():
#         async with aiofiles.open(file_path, "rb") as f:
#             while chunk := await f.read(DEFAULT_CHUNK_SIZE):
#                 yield chunk
#
#     return StreamingResponse(stream_file(), media_type="video/mp4")


# async def save_file_in_folder(image, road, resolution):
#     Path(f"./files/{road}").mkdir(parents=True, exist_ok=True)
#     image.save(f"./files/{road}/{resolution}.webp", format="webp")


# async def write_image_road(db: Session, post_id: uuid, image_road: str, order: int):
#     image_road_object = AdPhotos(url=image_road, ad_id=post_id, id=uuid.uuid4(), order=order)
#     db.add(image_road_object)
#     db.commit()
#     return True

