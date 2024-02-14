import hashlib
import io
import json
import os
import uuid

from unidecode import unidecode
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Union
from uuid import UUID
from PIL import Image
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, APIRouter, HTTPException, Form, UploadFile, File, responses, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import insert, and_, func, desc, update, delete
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased
from fastapi.staticfiles import StaticFiles
from app.api.auth import get_current_active_user, get_current_staff_user, get_current_active_user_or_none
# from fastapi_cache import FastAPICache
# from fastapi_cache.backends.redis import RedisBackend
# from redis import asyncio as aioredis
from app.database.database import get_async_session, create_tables
from app.models.admin_models import AdminUser
from app.models.models import Catalog, Item, ItemImages, ItemIngredients, item_ingredients_association, Orders, \
    Receipts, MinimalSumForOrder, PaymentState, StorePoint
from app.schemas.schemas import CatalogCreate, ItemResponse, ItemIngredientsOut, CatalogOut, CatalogCreatedOut, \
    ItemResponseReturn, OrderResponse, CreateOrderInput, CatalogInput, ItemIngredientsInput, \
    ItemIngredientsEdit, CategoryOut
from app.services.printer import print_receipt
from config import settings
from app.api import auth
from app.logger import setup_logger

PAYKEEPER_KEY = settings.PAYKEEPER_KEY

app = FastAPI(
    title=settings.TITLE,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    root_path=settings.OPENAPI_PREFIX,
    debug=True
)
app.mount("/static", StaticFiles(directory="static"), name="static")

router = APIRouter(prefix="/api/v2")

logger = setup_logger(__name__)


@router.get("/categories", response_model=List[CategoryOut], status_code=200)
async def get_all_categories(
        session: AsyncSession = Depends(get_async_session),
        current_user: Optional[AdminUser] = Depends(get_current_active_user_or_none)
):
    try:
        # async with session.begin():
        if current_user:
            catalogs = await session.execute(select(Catalog).order_by(Catalog.order))
        else:
            catalogs = await session.execute(select(Catalog).where(Catalog.slug != 'arkhiv').order_by(Catalog.order))

        # catalogs = await session.execute(select(Catalog).order_by(Catalog.order))
        catalogs = catalogs.scalars().all()

        logger.info("Категории")

        # Создаем список объектов CatalogOut для всех каталогов
        catalogs_response = []
        for catalog in catalogs:
            catalog_response = CategoryOut(
                id=catalog.id,
                title=catalog.title
            )
            catalogs_response.append(catalog_response)

        return catalogs_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog", response_model=List[CatalogOut], status_code=200)
async def get_all_catalogs(session: AsyncSession = Depends(get_async_session), current_user: Optional[AdminUser] = Depends(get_current_active_user_or_none)):
    try:
        # async with session.begin():
        if current_user:
            catalogs = await session.execute(select(Catalog).order_by(Catalog.order))
        else:
            catalogs = await session.execute(select(Catalog).where(Catalog.slug != 'arkhiv').order_by(Catalog.order))
            # catalogs = await session.execute(select(Catalog).order_by(Catalog.order))
        catalogs = catalogs.scalars().all()

        # Создаем список объектов CatalogOut для всех каталогов
        catalogs_response = []
        for catalog in catalogs:
            catalog_response = CatalogOut(
                id=catalog.id,
                title=catalog.title,
                slug=catalog.slug,
                order=catalog.order,
                items=[]  # Заполняется позже при запросе товаров для каждого каталога
            )
            catalogs_response.append(catalog_response)

            # Запросить товары для этого каталога и добавить их в список items
            catalog_items = await session.execute(
                select(Item).options(selectinload(Item.ingredients), selectinload(Item.images))
                .where(Item.catalog_id == catalog.id, Item.is_active == True).order_by(Item.order)
            )
            catalog_items = catalog_items.scalars().all()

            for item in catalog_items:
                item_response = ItemResponse(
                    id=item.id,
                    catalog_id=item.catalog_id,
                    title=item.title,
                    slug=item.slug,
                    price=item.price,
                    description=item.description,
                    in_stock=item.in_stock,
                    is_active=item.is_active,
                    out=item.out,
                    measure=item.measure,
                    order=item.order,
                    type=item.type,
                    tax=item.tax,
                    images=[image.id for image in item.images],
                    ingredients=[ingredient.name for ingredient in item.ingredients]
                )
                catalog_response.items.append(item_response)

        return catalogs_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalog/create", response_model=CatalogCreatedOut, dependencies=[Depends(get_current_active_user)])
async def create_catalog(
        catalog_data: CatalogInput,
        session: AsyncSession = Depends(get_async_session)
):
    try:
        title = catalog_data.title
        lowercase_title = title.lower()
        slug = unidecode(lowercase_title).replace(' ', '-')

        catalog_find_exist = await session.execute(select(Catalog).where(Catalog.slug == slug))
        catalog_find_exist = catalog_find_exist.scalar_one_or_none()
        if catalog_find_exist:
            raise HTTPException(status_code=404, detail="Категория с таким названием уже существует")

        catalog_create_data = CatalogCreate(title=title, slug=slug)
        stmt = insert(Catalog).values(**catalog_create_data.dict()).returning(Catalog)
        result = await session.execute(stmt)
        created_catalog = result.scalar_one()  # Получаем созданную запись

        await session.commit()
        logger.info(f"Создана категория: {title}")
        return created_catalog

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}", dependencies=[Depends(get_current_active_user)])
async def delete_category_by_id(category_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        catalogs = await session.execute(select(Catalog).where(Catalog.id == category_id))
        catalog = catalogs.scalars().one_or_none()

        if not catalog:
            raise HTTPException(status_code=404, detail="Категория не найдена")

        if catalog.slug == 'arkhiv':
            raise HTTPException(status_code=404, detail="Данная категория не может быть удалена")

        catalog_title = catalog.title
        await session.delete(catalog)
        await session.commit()
        logger.info(f"Удалена категория: {catalog_title}")

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше
    except Exception as e:
        raise HTTPException(status_code=404, detail="Ошибка удаления категории. Возможно в данной категории еще есть товары.")


@router.get("/items/{catalog_id}", status_code=200, dependencies=[Depends(get_current_staff_user)])
async def get_all_items_by_catalog_id(catalog_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        items = await session.execute(
            select(Item).options(
                selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.catalog_id == catalog_id, Item.is_active == True).order_by(Item.order)
        )
        items = items.scalars().all()

        # Создаем список объектов ItemResponse для всех товаров
        items_response = []
        for item in items:
            item_response = ItemResponse(
                id=item.id,
                catalog_id=item.catalog_id,
                title=item.title,
                slug=item.slug,
                price=item.price,
                description=item.description,
                in_stock=item.in_stock,
                is_active=item.is_active,
                out=item.out,
                measure=item.measure,
                order=item.order,
                type=item.type,
                tax=item.tax,
                images=[image.id for image in item.images],
                ingredients=[ingredient.name for ingredient in item.ingredients]
            )
            items_response.append(item_response)

        return items_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/item/{item_id}", status_code=200, dependencies=[Depends(get_current_active_user)])
async def get_item_by_id(item_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        items = await session.execute(
            select(Item).options(
                selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.id == item_id)
        )
        item = items.scalars().one_or_none()

        # Создаем список объектов ItemResponse для всех товаров
        item_response = ItemResponse(
            id=item.id,
            catalog_id=item.catalog_id,
            title=item.title,
            slug=item.slug,
            price=item.price,
            description=item.description,
            in_stock=item.in_stock,
            is_active=item.is_active,
            out=item.out,
            measure=item.measure,
            order=item.order,
            type=item.type,
            tax=item.tax,
            images=[image.id for image in item.images],
            ingredients=[ingredient.name for ingredient in item.ingredients]
        )
        # items_response.append(item_response)

        return item_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cart", status_code=200)
async def get_items_by_id_list(
        items_list: List[UUID],
        session: AsyncSession = Depends(get_async_session)
):
    try:
        async with session.begin():
            # Создаем список объектов ItemResponse для всех товаров
            items_response = []
            total = 0
            for item_id in items_list:
                items = await session.execute(
                    select(Item).options(
                        selectinload(Item.ingredients),
                        selectinload(Item.images)
                    ).where(Item.id == item_id, Item.is_active == True)
                )
                item = items.scalars().one_or_none()
                if item:
                    item_response = ItemResponse(
                        id=item.id,
                        catalog_id=item.catalog_id,
                        title=item.title,
                        slug=item.slug,
                        price=item.price,
                        description=item.description,
                        in_stock=item.in_stock,
                        is_active=item.is_active,
                        out=item.out,
                        measure=item.measure,
                        order=item.order,
                        type=item.type,
                        tax=item.tax,
                        images=[image.id for image in item.images],
                        ingredients=[ingredient.name for ingredient in item.ingredients]
                    )
                    items_response.append(item_response)
                    total += int(item.price)
            # return items_response

            query = select(func.count(Orders.id)).where(Orders.status == "готовится")
            order_count = await session.scalar(query)

            if 0 <= order_count < 10:
                wait_time = "10"
            elif 10 <= order_count < 20:
                wait_time = "20"
            elif order_count >= 20:
                wait_time = "30"
            else:
                wait_time = "10"

        min_total = await get_minimal_sum_for_order(session)
        payment = await get_payment_state(session)

        store_points = await session.execute(select(StorePoint).order_by(StorePoint.id))
        store_points = store_points.scalars().all()

        if store_points is None:
            raise HTTPException(status_code=404, detail="ПВЗ не найдены")

        response = {
            "payment": payment,
            "waiting": wait_time,
            "min_total": min_total.sum,
            "total": total,
            "items": items_response,
            "store": store_points
        }
        return response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items", status_code=200, dependencies=[Depends(get_current_staff_user)])
async def get_all_items(session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        items = await session.execute(
            select(Item).options(
                selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.is_active == True).order_by(Item.order)
        )
        items = items.scalars().all()

        # Создаем список объектов ItemResponse для всех товаров
        items_response = []
        for item in items:
            item_response = ItemResponse(
                id=item.id,
                catalog_id=item.catalog_id,
                title=item.title,
                slug=item.slug,
                price=item.price,
                description=item.description,
                in_stock=item.in_stock,
                is_active=item.is_active,
                out=item.out,
                measure=item.measure,
                order=item.order,
                type=item.type,
                tax=item.tax,
                images=[image.id for image in item.images],
                ingredients=[ingredient.name for ingredient in item.ingredients]
            )
            items_response.append(item_response)

        return items_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingredients", status_code=200, dependencies=[Depends(get_current_active_user)])
async def get_all_ingredients(session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        ingredients = await session.execute(
            select(ItemIngredients).order_by(ItemIngredients.order)
        )
        ingredients = ingredients.scalars().all()

        # Создаем список объектов ItemResponse для всех товаров
        ingredients_response = []
        for ingredient in ingredients:
            ingredient_response = ItemIngredientsOut(
                id=ingredient.id,
                name=ingredient.name,
                order=ingredient.order
            )
            ingredients_response.append(ingredient_response)

        return ingredients_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingredients/create", status_code=201, dependencies=[Depends(get_current_active_user)])
async def create_item_ingredients(
        ingredients: ItemIngredientsInput,
        session: AsyncSession = Depends(get_async_session)
):
    try:
        name = ingredients.name

        # async with session.begin():
        new_item_ingredient = ItemIngredients(name=name)
        session.add(new_item_ingredient)
        await session.commit()
        await session.flush()
        logger.info(f"Создан ингредиент: {name}")
        return new_item_ingredient

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/create", status_code=201, dependencies=[Depends(get_current_active_user)])
async def create_item(
        catalog_id: UUID = Form(...),
        title: str = Form(...),
        price: int = Form(...),
        description: str = Form(None),
        in_stock: bool = Form(True),
        out: int = Form(...),
        measure: str = Form(...),
        ingredients: str = Form(None),
        images: List[UploadFile] = File(...),  # Загрузка изображений - можно создавать без фото
        session: AsyncSession = Depends(get_async_session)
):
    try:
        # async with session.begin():
        stmt = select(Catalog).where(and_(Catalog.id == catalog_id))
        catalog = await session.execute(stmt)
        catalog = catalog.scalar_one_or_none()

        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        # slug = slugify(title)
        lowercase_title = title.lower()
        slug = unidecode(lowercase_title).replace(' ', '-')
        # Создать новый товар
        new_item = Item(
            catalog_id=catalog_id,
            title=title,
            slug=slug,
            price=price,
            description=description,
            in_stock=in_stock,
            out=out,
            measure=measure,
            type="goods",
            tax=None
        )

        session.add(new_item)
        try:
            await session.flush()
        except:
            raise HTTPException(status_code=404, detail=f"Блюдо с названием `{title}` уже существует")
        # await session.flush()
        logger.info(f"Создан товар: {title}")
        # Добавить изображения товара (если есть)
        if images:
            for image in images:
                image_data = await image.read()

                road = uuid.uuid4()

                im = Image.open(io.BytesIO(image_data))
                im = im.convert("RGB")
                # await save_image_square(image=im, road=road)
                await save_file_in_folder(im, road)
                await write_image_road(session, new_item.id, road)

        # Собрать ингредиенты (если есть)
        ingredients_list = json.loads(ingredients) if ingredients else []
        if ingredients_list:
            for ingredient_name in ingredients_list:
                stmt = select(ItemIngredients).where(ItemIngredients.name == ingredient_name)
                ingredient = await session.execute(stmt)
                ingredient = ingredient.scalar_one_or_none()
                if ingredient:
                    # Добавляем ингредиент к новому товару
                    await session.execute(
                        item_ingredients_association.insert().values(
                            item_id=new_item.id,
                            ingredient_id=ingredient.id
                        )
                    )

        try:
            await session.commit()  # Завершить транзакцию
        except:
            raise HTTPException(status_code=404, detail="Ошибка создания товара")

        # Здесь добавляем код для загрузки ингредиентов и изображений
        async with session.begin():
            item = await session.execute(
                select(Item).options(
                    selectinload(Item.ingredients),
                    selectinload(Item.images)
                ).where(Item.id == new_item.id)
            )
            item = item.scalar_one()

        # Вернуть собранные данные в формате ItemResponse
        item_response = ItemResponse(
            id=item.id,
            catalog_id=item.catalog_id,
            title=item.title,
            slug=item.slug,
            price=item.price,
            description=item.description,
            in_stock=item.in_stock,
            is_active=item.is_active,
            out=item.out,
            measure=item.measure,
            order=item.order,
            type=item.type,
            tax=item.tax,
            images=[image.id for image in item.images],
            ingredients=[ingredient.name for ingredient in item.ingredients]
        )
        return item_response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order/create", status_code=201)
async def create_order(input_data: CreateOrderInput, session: AsyncSession = Depends(get_async_session)):
    try:
        async with session.begin():
            items = input_data.order_items
            num = await generate_order_number(session)

            new_order = Orders(num=num, client=input_data.client, delivery=input_data.delivery,
                               cutlery=input_data.cutlery, comment=input_data.comment, order_id=input_data.order_id)
            for item in items:
                order_receipts = Receipts(item_id=item.id, order_id=new_order.id, amount=item.amount)
                new_order.receipts.append(order_receipts)

            session.add(new_order)
            await session.commit()
            logger.info(f"Создан заказ: {num}")
            return {"message": "Заказ успешно создан"}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", status_code=200, dependencies=[Depends(get_current_staff_user)])
async def get_all_orders(
        status: Optional[str] = None,
        date_filter: Optional[date] = None,
        today: Optional[bool] = False,
        page: int = 1,
        limit: int = Query(default=50, lte=100),
        session: AsyncSession = Depends(get_async_session)
):
    offset = (page - 1) * limit
    try:
        # async with session.begin():
        query = select(Orders).order_by(desc(Orders.created_at))

        if status:
            query = query.where(Orders.status == status)
        else:
            query = query.where(Orders.status != 'ожидает')

        if date_filter:
            query = query.where(func.date(Orders.created_at) == date_filter)

        if today:
            today = date.today()
            query = query.where(func.date(Orders.created_at) == today)

        total = await session.execute(select(func.count()).select_from(query.alias()))
        total_count = total.scalar_one()

        orders = await session.execute(query.offset(offset).limit(limit))
        orders_list = orders.scalars().all()  # Преобразование в список

        orders_response = []
        for order in orders_list:
            items_response, total_sum = await get_items_to_order(order.id, session)
            order_response = OrderResponse(
                id=order.id,
                order_id=order.order_id,
                num=order.num,
                client=order.client,
                delivery=order.delivery,
                cutlery=order.cutlery,
                comment=order.comment,
                status=order.status,
                created_at=order.created_at,
                items=items_response,
                total=total_sum
            )
            orders_response.append(order_response)

        return {"total": total_count, "orders": orders_response}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    # try:
    #     async with session.begin():
    #         items_alias = aliased(Item)
    #         receipts_alias = aliased(Receipts)
    #
    #         items = await session.execute(
    #             select(items_alias, receipts_alias)
    #             .join(receipts_alias, receipts_alias.item_id == items_alias.id)
    #             .where(receipts_alias.order_id == order_id)
    #             .options(
    #                 joinedload(items_alias.ingredients),
    #                 joinedload(items_alias.images)
    #             )
    #         )
    #
    #         items_response = []
    #         for item, receipt in items.unique():
    #             item_response = ItemResponseReturn(
    #                 id=item.id,
    #                 title=item.title,
    #                 slug=item.slug,
    #                 price=item.price,
    #                 description=item.description,
    #                 in_stock=item.in_stock,
    #                 out=item.out,
    #                 measure=item.measure,
    #                 images=[image.id for image in item.images],
    #                 ingredients=[ingredient.name for ingredient in item.ingredients],
    #                 amount=receipt.amount
    #             )
    #             items_response.append(item_response)
    #
    #     return items_response
    #
    # except Exception as e:
    #     await session.rollback()
    #     raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}", status_code=200, dependencies=[Depends(get_current_staff_user)])
async def get_order_by_id(order_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():

        order = await session.execute(
            select(Orders).where(Orders.order_id == order_id)
        )
        order = order.scalars().one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Order Not found")

        items_response, total_sum = await get_items_to_order(order.id, session)
        order_response = OrderResponse(
            id=order.id,
            order_id=order.order_id,
            num=order.num,
            client=order.client,
            delivery=order.delivery,
            cutlery=order.cutlery,
            comment=order.comment,
            status=order.status,
            created_at=order.created_at,
            items=items_response,
            total=total_sum
        )

        return order_response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}/status", status_code=200)
async def get_order_status_by_id(order_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        async with session.begin():

            order = await session.execute(
                select(Orders.status).where(Orders.id == order_id)
            )
            order = order.scalars().one_or_none()

            if not order:
                raise HTTPException(status_code=404, detail="Order Not found")

            order_response = {"status": order}

            return order_response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/image/{image_id}", status_code=200, response_class=responses.FileResponse)
async def get_item_image_by_id(image_id: UUID, session: AsyncSession = Depends(get_async_session)):
    image = await get_image_by_uuid(image_id, session)
    if not image:
        raise HTTPException(status_code=404, detail="Not found")
    image = f"./static/item_images/{image.url}"

    if not Path(image).is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return image


async def get_items_to_order(order_id, session):
    items_alias = aliased(Item)
    receipts_alias = aliased(Receipts)
    items = await session.execute(
        select(items_alias, receipts_alias)
        .join(receipts_alias, receipts_alias.item_id == items_alias.id)
        .where(receipts_alias.order_id == order_id)
    )
    items_response = []
    total_sum = 0

    for item, receipt in items:
        item_sum = item.price * receipt.amount
        total_sum += item_sum

        item_response = ItemResponseReturn(
            id=item.id,
            title=item.title,
            slug=item.slug,
            price=item.price,
            description=item.description,
            in_stock=item.in_stock,
            out=item.out,
            measure=item.measure,
            amount=receipt.amount,
            sum=item_sum
        )
        items_response.append(item_response)

    return items_response, total_sum


async def generate_order_number(session: AsyncSession) -> str:
    today = datetime.now()
    formatted_date = today.strftime("%Y%m%d")
    # Получаем количество заказов за текущий день
    order_count = await session.execute(
        select(func.count(Orders.id))
        .where(func.date_trunc("day", Orders.created_at) == today.date())
    )
    order_count = order_count.scalar()

    # Форматируем номер заказа так, чтобы он всегда содержал 5 цифр в конце
    order_number = f"{formatted_date}-{order_count + 1:05d}"

    return order_number


def format_order_for_print(order):
    cutlery = '-' if not order.cutlery or order.cutlery == 0 else order.cutlery
    comment = '-' if not order.comment or order.comment == '' else order.comment

    formatted_order = f"Номер заказа: {order.num}\n"
    formatted_order += "Заказ:\n"

    for item in order.items:
        formatted_order += f"  {item.title} - {item.amount} шт.\n"

    formatted_order += "\n"
    formatted_date = order.created_at.strftime("%d.%m.%Y - %H:%M")
    formatted_order += f"Заказ создан: {formatted_date}\n"
    formatted_order += f"Кол-во приборов: {cutlery}\n"
    formatted_order += f"Комментарий: {comment}\n"

    formatted_order += f"Клиент: {order.client}\n"
    formatted_order += f"Доставка: {order.delivery}\n"
    # print(formatted_order)
    return formatted_order


async def get_image_by_uuid(image_id, session):
    async with session.begin():
        db_image = await session.execute(
            select(ItemImages).where(ItemImages.id == image_id)
        )
        db_image = db_image.scalars().one_or_none()
    if db_image:
        return db_image
    else:
        return False


# not user already
async def save_image_square(image, road):
    width, height = image.size
    if width > height:
        cropped = (width - height) / 2
        im = image.crop((cropped, 0, width - cropped, height))
        im = im.resize((500, 500))
    elif width < height:
        cropped = (height - width) / 2
        im = image.crop((0, cropped, width, height - cropped))
        im = im.resize((500, 500))
    else:
        im = image.resize((500, 500))
    await save_file_in_folder(im, road)


async def write_image_road(session, item_id, road):
    image_record = ItemImages(
        item_id=item_id,
        alt="Фудкорт Трактор",
        url=f"{road}.webp"
    )
    session.add(image_record)
    return True


async def save_file_in_folder(image, road):
    Path(f"./static/item_images").mkdir(parents=True, exist_ok=True)
    image.save(f"./static/item_images/{road}.webp", format="webp")


@router.patch("/item/{item_id}/change", status_code=202, dependencies=[Depends(get_current_staff_user)])
async def change_item_status_by_id(item_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        items = await session.execute(
            select(Item).options(
                selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.id == item_id)
        )
        item = items.scalars().one_or_none()

        # Toggle the 'in_stock' field
        new_in_stock = not item.in_stock

        # Update the 'in_stock' field in the database
        item.in_stock = new_in_stock
        await session.commit()
        logger.info(f"Наличие товара `{item.title}`: {new_in_stock}")
        item_response = ItemResponse(
            id=item.id,
            catalog_id=item.catalog_id,
            title=item.title,
            slug=item.slug,
            price=item.price,
            description=item.description,
            in_stock=item.in_stock,
            is_active=item.is_active,
            out=item.out,
            measure=item.measure,
            order=item.order,
            type=item.type,
            tax=item.tax,
            images=[image.id for image in item.images],
            ingredients=[ingredient.name for ingredient in item.ingredients]
        )

        return item_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/item/{item_id}/edit", status_code=202, dependencies=[Depends(get_current_active_user)])
async def edit_item_by_id(
        item_id: UUID,
        catalog_id: UUID = Form(None),
        title: str = Form(None),
        price: int = Form(None),
        description: str = Form(None),
        in_stock: bool = Form(None),
        out: int = Form(None),
        measure: str = Form(None),
        ingredients: str = Form(None),
        old_images: str = Form(None),
        images: List[UploadFile] = File(None),
        session: AsyncSession = Depends(get_async_session)
):
    if old_images is None and images is None:
        raise HTTPException(status_code=400, detail="Должно быть загружено хотя бы одно изображение")

    try:
        old_images_list = json.loads(old_images)
    except:
        raise HTTPException(status_code=400, detail="Должно быть загружено хотя бы одно изображение")

    try:
        # async with session.begin():
        # Получить существующий товар
        item = await session.execute(
            select(Item).options(
                # selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.id == item_id)
        )
        item = item.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Удалить старые изображения, которых нет в списке old_images
        if old_images_list is not None:
            for image in item.images:
                if str(image.id) not in old_images_list:
                    await delete_image_and_record(session, image)

        # Добавить новые изображения
        if images is not None:
            for image in images:
                image_data = await image.read()
                road = uuid.uuid4()
                im = Image.open(io.BytesIO(image_data))
                im = im.convert("RGB")

                # await save_image_square(image=im, road=road)
                await save_file_in_folder(im, road)
                await write_image_road(session, item.id, road)

        # Обновить поля товара, если переданы новые значения
        if title is not None:
            lowercase_title = title.lower()
            slug = unidecode(lowercase_title).replace(' ', '-')
            if item.slug != slug:
                check_item_names = await session.execute(
                    select(Item).options(
                        # selectinload(Item.ingredients),
                        selectinload(Item.images)
                    ).where(Item.slug == slug)
                )
                check_item_names = check_item_names.scalar_one_or_none()

                if check_item_names:
                    raise HTTPException(status_code=404, detail=f"Блюдо с названием `{title}` уже существует")

                item.title = title
                item.slug = slug

        if price is not None:
            item.price = price
        if description is not None:
            item.description = description
        if in_stock is not None:
            item.in_stock = in_stock
        if out is not None:
            item.out = out
        if measure is not None:
            item.measure = measure

        # if type is not None:
        #     item.type = type
        # if tax is not None:
        #     item.tax = tax

        if catalog_id is not None:
            item.catalog_id = catalog_id
        if ingredients is not None:
            ingredients_list = json.loads(ingredients)
            # item.ingredients.clear()  # Удаляем существующие ингредиенты
            await session.execute(
                item_ingredients_association.delete().where(item_ingredients_association.c.item_id == item_id)
            )

            for ingredient_name in ingredients_list:
                stmt = select(ItemIngredients).where(ItemIngredients.name == ingredient_name)
                ingredient = await session.execute(stmt)
                ingredient = ingredient.scalar_one_or_none()
                if ingredient:
                    await session.execute(
                        item_ingredients_association.insert().values(item_id=item_id, ingredient_id=ingredient.id)
                    )

        await session.commit()  # Завершить транзакцию
        logger.info(f"Отредактирован товар: {item.title}")
        session.expire(item, ['images'])
        session.expire(item, ['ingredients'])

        async with session.begin():
            # Здесь добавляем код для загрузки ингредиентов и изображений (аналогично другим эндпоинтам)
            new_item = await session.execute(
                select(Item).options(
                    selectinload(Item.ingredients),
                    selectinload(Item.images)
                ).where(Item.id == item.id)
            )
            new_item = new_item.scalar_one()

            # Вернуть обновленные данные в формате ItemResponse
            item_response = ItemResponse(
                id=new_item.id,
                catalog_id=new_item.catalog_id,
                title=new_item.title,
                slug=new_item.slug,
                price=new_item.price,
                description=new_item.description,
                in_stock=new_item.in_stock,
                is_active=item.is_active,
                out=new_item.out,
                measure=new_item.measure,
                order=new_item.order,
                type=item.type,
                tax=item.tax,
                images=[image.id for image in new_item.images],
                ingredients=[ingredient.name for ingredient in new_item.ingredients]
            )
            return item_response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/{item_id}/change", status_code=202, dependencies=[Depends(get_current_active_user)])
async def change_item_is_active_by_id(item_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        items = await session.execute(
            select(Item).options(
                selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.id == item_id)
        )
        item = items.scalars().one_or_none()

        # Toggle the 'is_active' field
        new_is_active = not item.is_active
        # Toggle the 'in_stock' field
        new_in_stock = False

        # Update the 'in_stock' field in the database
        item.in_stock = new_in_stock
        # Update the 'is_active' field in the database
        item.is_active = new_is_active
        await session.commit()
        logger.info(f"Товар `{item.title}` активирован: {new_is_active}")
        item_response = ItemResponse(
            id=item.id,
            catalog_id=item.catalog_id,
            title=item.title,
            slug=item.slug,
            price=item.price,
            description=item.description,
            in_stock=item.in_stock,
            is_active=item.is_active,
            out=item.out,
            measure=item.measure,
            order=item.order,
            type=item.type,
            tax=item.tax,
            images=[image.id for image in item.images],
            ingredients=[ingredient.name for ingredient in item.ingredients]
        )

        return item_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def delete_image_and_record(session: AsyncSession, image: ItemImages):
    await session.delete(image)
    # Удалить файл изображения
    image_path = f"./static/item_images/{image.url}"
    try:
        # if os.path.exists(image_path):
        # shutil.rmtree(os.path.dirname(image_path))
        # shutil.rmtree(image_path)
        os.remove(image_path)
    except OSError:
        pass


@router.get("/archive/items", status_code=200, dependencies=[Depends(get_current_active_user)])
async def get_archived_items(session: AsyncSession = Depends(get_async_session)):
    try:
        # async with session.begin():
        items = await session.execute(
            select(Item).options(
                selectinload(Item.ingredients),
                selectinload(Item.images)
            ).where(Item.is_active == False).order_by(Item.order)
        )
        items = items.scalars().all()

        # Создаем список объектов ItemResponse для всех товаров
        items_response = []
        for item in items:
            item_response = ItemResponse(
                id=item.id,
                catalog_id=item.catalog_id,
                title=item.title,
                slug=item.slug,
                price=item.price,
                description=item.description,
                in_stock=item.in_stock,
                is_active=item.is_active,
                out=item.out,
                measure=item.measure,
                order=item.order,
                type=item.type,
                tax=item.tax,
                images=[image.id for image in item.images],
                ingredients=[ingredient.name for ingredient in item.ingredients]
            )
            items_response.append(item_response)

        return items_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/ordering/{selected}", status_code=200, dependencies=[Depends(get_current_active_user)])
async def change_ordering(selected: str, items_list: List[Dict[str, Union[str, int]]],
                          session: AsyncSession = Depends(get_async_session)):
    """
    Изменение порядка отображения товаров, категорий и ингредиентов.

    Параметры:
    - selected: items | catalog | ingredients.
    - items_list: [ {"id": "UUID", "order": int} ].
    - session: AsyncSession.
    Возвращает:
    - message: str
    """
    try:
        # async with session.begin():
        for item_info in items_list:
            item_id = item_info["id"]
            item_order = item_info["order"]

            if selected == 'items':
                await session.execute(
                    update(Item)
                    .where(Item.id == item_id)
                    .values(order=item_order)
                )
            elif selected == 'catalog':
                await session.execute(
                    update(Catalog)
                    .where(Catalog.id == item_id)
                    .values(order=item_order)
                )
            elif selected == 'ingredients':
                await session.execute(
                    update(ItemIngredients)
                    .where(ItemIngredients.id == item_id)
                    .values(order=item_order)
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid 'select' parameter")

        await session.commit()
        return {"message": "Порядок был успешно изменен"}

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/order/{order_id}/{status}", status_code=202, dependencies=[Depends(get_current_staff_user)])
async def change_order_status_by_id(order_id: UUID, status: str, session: AsyncSession = Depends(get_async_session)):
    status_mapping = {
        "created": "создан",
        "waiting": "ожидает",
        "serving": "готовится",
        "ready": "готов",
        "canceled": "отменен"
    }

    if status not in status_mapping:
        raise HTTPException(status_code=400, detail="Статус заказа указан неправильно")

    new_status = status_mapping[status]

    try:
        # async with session.begin():
        orders = await session.execute(
            select(Orders).where(Orders.id == order_id)
        )
        order = orders.scalars().one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")

        order.status = new_status
        order.updated_at = datetime.now()  # Обновляем поле updated_at
        await session.commit()

        async with session.begin():
            items_response, total_sum = await get_items_to_order(order.id, session)
            order_response = OrderResponse(
                id=order.id,
                order_id=order.order_id,
                num=order.num,
                client=order.client,
                delivery=order.delivery,
                cutlery=order.cutlery,
                comment=order.comment,
                status=order.status,
                created_at=order.created_at,
                items=items_response,
                total=total_sum
            )
            return order_response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order/confirm", status_code=200)
async def confirm_order(
        request: Request,
        session: AsyncSession = Depends(get_async_session)
):

    confirm_data = await request.form()
    confirm_data_id = confirm_data.get("id")
    confirm_data_sum = confirm_data.get("sum")
    confirm_data_clientid = confirm_data.get("clientid")
    confirm_data_orderid = confirm_data.get("orderid")
    confirm_data_key = confirm_data.get("key")

    concatenated_params = (
        f"{confirm_data_id}{confirm_data_sum}{confirm_data_clientid}"
        f"{confirm_data_orderid}{PAYKEEPER_KEY}"
    )
    hash_object = hashlib.md5(concatenated_params.encode())
    calculated_key = hash_object.hexdigest()
    # calculated_key = 'KmC(tKKKZ7wOVqVAZ'

    if confirm_data_key != calculated_key:
        raise HTTPException(status_code=400, detail="Error! Hash mismatch")

    order_id = confirm_data_orderid
    client = confirm_data_clientid
    response_data = "OK " + hashlib.md5((confirm_data_id + PAYKEEPER_KEY).encode()).hexdigest()

    try:
        async with session.begin():
            order = await session.execute(
                select(Orders).where(Orders.order_id == order_id, Orders.client == client)
            )
            order = order.scalar_one_or_none()

            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")

            # if order.status != "ожидает":
            if order.is_paid:
                return PlainTextResponse(content=response_data)

            order.status = "готовится"
            order.updated_at = datetime.now()  # Обновляем поле updated_at
            order.is_paid = True

            logger.info(f"Заказ `{order.num}`: Оплачен и Подтвержден")
            items_response, total_sum = await get_items_to_order(order.id, session)
            contacts = order.client
            level = int(order.delivery[0])
            order_json = {
                "order_number": order.num,
                "items": [item.__dict__ for item in items_response],
                "total": total_sum,
                "contacts": contacts,
                "level": level
            }
            # ФОРМИРУЕМ ЗАКАЗ НА ПЕЧАТЬ !!!
            print_receipt(order_json)
            await session.commit()
            return PlainTextResponse(content=response_data)

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/catalog/{catalog_id}/edit", response_model=CatalogCreatedOut,
              dependencies=[Depends(get_current_active_user)])
async def edit_catalog(
        catalog_id: UUID,
        input_data: CatalogInput,
        session: AsyncSession = Depends(get_async_session)
):
    try:
        new_title = input_data.title
        lowercase_title = new_title.lower()
        new_slug = unidecode(lowercase_title).replace(' ', '-')

        catalog_find_exist = await session.execute(select(Catalog).where(Catalog.slug == new_slug))
        catalog_find_exist = catalog_find_exist.scalar_one_or_none()
        if catalog_find_exist:
            raise HTTPException(status_code=404, detail="Категория с таким названием уже существует")

        catalog = await session.execute(select(Catalog).where(Catalog.id == catalog_id))
        catalog = catalog.scalar_one_or_none()

        if catalog.slug == 'arkhiv':
            raise HTTPException(status_code=404, detail="Данная категория не может быть изменена")

        if not catalog:
            raise HTTPException(status_code=404, detail="Категория не найдена")

        old_title = catalog.title

        # Проверяем, изменился ли title и требуется ли обновление slug
        if new_title != catalog.title and new_slug != catalog.slug:
            catalog.title = new_title
            catalog.slug = new_slug
        else:
            raise HTTPException(status_code=404, detail="Категория с таким названием уже существует")

        await session.commit()
        logger.info(f"Категория `{old_title}` изменена на `{new_title}`")
        return catalog

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/get", status_code=200)
async def get_orders_by_id_list(order_ids: List[UUID], session: AsyncSession = Depends(get_async_session)):
    orders_response = []
    try:
        async with session.begin():
            orders = await session.execute(
                select(Orders)
                .where(Orders.order_id.in_(order_ids))
                .where(Orders.status != 'ожидает')
                .order_by(Orders.updated_at.desc())
            )

            orders = orders.scalars().all()

            if not orders:
                raise HTTPException(status_code=404, detail="Заказы не найдены")

            for order in orders:
                items_response, total_sum = await get_items_to_order(order.id, session)
                order_response = OrderResponse(
                    id=order.id,
                    order_id=order.order_id,
                    num=order.num,
                    client=order.client,
                    delivery=order.delivery,
                    cutlery=order.cutlery,
                    comment=order.comment,
                    status=order.status,
                    created_at=order.created_at,
                    items=items_response,
                    total=total_sum
                )
                orders_response.append(order_response)

            return orders_response

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# # временный эндпоинт для активации
# @router.get("/orders/{order_id}/activate", status_code=202)
# async def activate_order_by_id(order_id: UUID, session: AsyncSession = Depends(get_async_session)):
#     try:
#         async with session.begin():
#             order = await session.execute(
#                 select(Orders).where(Orders.order_id == order_id)
#             )
#             order = order.scalar_one_or_none()
#
#             if not order:
#                 raise HTTPException(status_code=404, detail="Заказ не найден")
#
#             if order.status == "ожидает":
#                 order.status = "готовится"
#                 order.updated_at = datetime.now()  # Обновляем поле updated_at
#                 items_response, total_sum = await get_items_to_order(order.id, session)
#                 order_json = {
#                     "order_number": order.num,
#                     "items": [item.__dict__ for item in items_response],  # items_response
#                     "total": total_sum,
#                     "level": 2
#                 }
#
#                 print_receipt(order_json)  # print receipt on app/service/printer.py
#                 await session.commit()
#             return
#
#     except HTTPException:  # Перехватываем исключение HTTPException
#         raise  # Перебрасываем его дальше
#
#     except Exception as e:
#         await session.rollback()
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("/total/get", status_code=202, dependencies=[Depends(get_current_active_user)])
async def get_min_sum_for_order(session: AsyncSession = Depends(get_async_session)):
    try:
        min_total = await get_minimal_sum_for_order(session)
        return {"min_total": min_total.sum}
    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/total/edit/{total}", status_code=202, dependencies=[Depends(get_current_active_user)])
async def edit_min_sum_for_order(
        total: int,
        session: AsyncSession = Depends(get_async_session)
):
    try:
        min_total = await edit_minimal_sum_for_order(total, session)
        logger.info(f"Минимальная сумма заказа изменена на `{min_total}`")
        return {"min_total": min_total}
    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def get_payment_state(session):
    try:
        state = await session.execute(
            select(PaymentState.state).where(PaymentState.id == 1)
        )
        state = state.scalar_one_or_none()
        if state is None:
            raise HTTPException(status_code=404, detail="Статус оплаты не найден")
        return state

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def get_minimal_sum_for_order(session):
    try:
        min_sum = await session.execute(
            select(MinimalSumForOrder).where(MinimalSumForOrder.id == 1)
        )
        min_sum = min_sum.scalar_one_or_none()

        if not min_sum:
            raise HTTPException(status_code=404, detail="Минимальная сумма заказа не найдена")
        return min_sum

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def edit_minimal_sum_for_order(total, session):
    try:
        min_sum = await get_minimal_sum_for_order(session)
        min_sum.sum = total
        print(min_sum.sum)
        await session.commit()

        return min_sum.sum

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingredients/{ingredient_id}", status_code=202, dependencies=[Depends(get_current_active_user)])
async def get_ingredient_by_id(ingredient_id: int, session: AsyncSession = Depends(get_async_session)):
    try:
        ingredient = await session.execute(
            select(ItemIngredients).where(ItemIngredients.id == ingredient_id)
        )
        ingredient = ingredient.scalar_one_or_none()

        if not ingredient:
            raise HTTPException(status_code=404, detail="Ингредиент не найден")

        return ingredient

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/ingredients/{ingredient_id}/edit", status_code=202, dependencies=[Depends(get_current_active_user)])
async def edit_ingredients(ingredient_id: int, input_data: ItemIngredientsEdit,
                           session: AsyncSession = Depends(get_async_session)):
    try:
        ingredient = await session.execute(
            select(ItemIngredients).where(ItemIngredients.id == ingredient_id)
        )
        ingredient = ingredient.scalar_one_or_none()

        if not ingredient:
            raise HTTPException(status_code=404, detail="Ингредиент не найден")
        old_ingredient_name = ingredient.name
        ingredient_name = input_data.name
        ingredient.name = ingredient_name
        await session.commit()
        logger.info(f"Ингредиент `{old_ingredient_name}` изменен на `{ingredient_name}`")
        return ingredient

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/ingredients/{ingredient_id}", status_code=202, dependencies=[Depends(get_current_active_user)])
async def delete_ingredient_by_id(ingredient_id: int, session: AsyncSession = Depends(get_async_session)):
    try:
        ingredient = await session.get(ItemIngredients, ingredient_id)

        if not ingredient:
            raise HTTPException(status_code=404, detail="Ингредиент не найден")

        # Удалить связанные записи из item_ingredients_association
        await session.execute(
            item_ingredients_association.delete().where(
                item_ingredients_association.c.ingredient_id == ingredient_id)
        )

        await session.delete(ingredient)  # Удаление ингредиента
        await session.commit()
        return {"message": "Ингредиент успешно удален"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/item/{item_id}/delete", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_item_by_id(item_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        # Get the existing item
        item = await session.execute(
            select(Item).options(
                selectinload(Item.images),
                selectinload(Item.ingredients)
            ).where(Item.id == item_id)
        )
        item = item.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Delete associated images
        for image in item.images:
            await delete_image_and_record(session, image)

        # Delete associated ingredients
        await session.execute(
            item_ingredients_association.delete().where(item_ingredients_association.c.item_id == item_id)
        )

        # Delete the item
        await session.delete(item)
        await session.commit()

        logger.info(f"Удален товар: {item.title}")

    except HTTPException:
        raise

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/order/{order_id}/delete", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_order_by_id(order_id: UUID, session: AsyncSession = Depends(get_async_session)):
    try:
        order = await session.execute(
            select(Orders).options(
                selectinload(Orders.receipts)
            ).where(Orders.id == order_id)
        )
        order = order.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Delete associated receipts
        for receipt in order.receipts:
            await session.delete(receipt)

        # Delete the order
        await session.delete(order)
        await session.commit()

        logger.info(f"Удален заказ: {order_id}")

    except HTTPException:
        raise

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/orders/delete-all", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_all_orders(session: AsyncSession = Depends(get_async_session)):
    try:
        # Удаляем все связанные записи из таблицы receipts
        await session.execute(delete(Receipts))

        # Удаляем все заказы
        await session.execute(delete(Orders))

        await session.commit()

        logger.info("Все заказы успешно удалены")

    except HTTPException:
        raise

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment/get", status_code=200, dependencies=[Depends(get_current_active_user)])
async def get_payment(session: AsyncSession = Depends(get_async_session)):
    try:
        payment = await get_payment_state(session)
        return {"payment": payment}
    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment/{key}", status_code=200, dependencies=[Depends(get_current_active_user)])
async def set_payment(key: str, session: AsyncSession = Depends(get_async_session)):
    try:
        payment = await session.get(PaymentState, 1)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        if key == 'set_true' and not payment.state:
            payment.state = True
            await session.commit()
            print('Set', payment.state)
        elif key == 'set_false' and payment.state:
            payment.state = False
            await session.commit()
            print('Set', payment.state)

        return {"payment": payment.state}
    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/store", status_code=200, dependencies=[Depends(get_current_active_user)])
async def get_store_point(session: AsyncSession = Depends(get_async_session)):
    try:
        store_points = await session.execute(select(StorePoint).order_by(StorePoint.id))
        store_points = store_points.scalars().all()

        if store_points is None:
            raise HTTPException(status_code=404, detail="ПВЗ не найдены")

        return store_points

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/store/{key}", status_code=200, dependencies=[Depends(get_current_active_user)])
async def edit_store_point_state(key: int, session: AsyncSession = Depends(get_async_session)):
    try:
        store_point = await session.execute(select(StorePoint).where(StorePoint.id == key))
        store_point = store_point.scalar_one_or_none()

        if store_point is None:
            raise HTTPException(status_code=404, detail="ПВЗ не найден")

        store_point.state = not store_point.state

        await session.commit()

        return store_point

    except HTTPException:  # Перехватываем исключение HTTPException
        raise  # Перебрасываем его дальше

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


router.include_router(auth.router)
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.openapi_url = "/arena-delivery/openapi.json"  # prod


# app.openapi_url = "/openapi.json"  # local


@app.on_event("startup")
async def startup_event():
    pass

    # await create_tables()
    # redis = aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", encoding="utf8", decode_responses=True)
    # FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
