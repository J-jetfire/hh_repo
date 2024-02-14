import json
import requests
import random
import uuid
import asyncio
from sqlalchemy import select
from app.database.database import get_async_session
from app.models.models import Item


async def get_items(session):
    items = await session.execute(
        select(Item).where(Item.is_active == True).order_by(Item.order)
    )
    items = items.scalars().all()

    # Получите список доступных item_id
    available_item_ids = [item.id for item in items]
    return available_item_ids


# Функция для создания случайных данных заказа
async def generate_random_order_data(available_item_ids):
    order_items = []
    num_order_items = random.randint(1, 10)

    for _ in range(num_order_items):
        order_item_id = random.choice(available_item_ids)
        order_item = {
            "id": str(order_item_id),
            "amount": random.randint(1, 10)
        }
        order_items.append(order_item)

    client = "799" + ''.join([str(random.randint(0, 9)) for _ in range(8)])

    x = random.randint(1, 15)
    y = random.randint(1, 28)
    z = random.randint(1, 40)
    delivery = f"{x} сектор, {y} ряд, {z} место"

    comment = ""
    cutlery = random.randint(1, 10)
    order_id = uuid.uuid4()

    order_data = {
        "order_items": order_items,
        "client": client,
        "delivery": delivery,
        "comment": comment,
        "cutlery": cutlery,
        "order_id": str(order_id)
    }
    print('order_data', order_data)
    return order_data


# Функция для создания n заказов
async def create_orders(n, available_item_ids):
    for _ in range(n):
        order_data = await generate_random_order_data(available_item_ids)
        order_data_json = json.dumps(order_data, default=str, ensure_ascii=False)
        print('order_data_json', order_data_json)

        response = requests.post("http://192.168.88.191:8080/api/v2/order/create", json=order_data)

        if response.status_code == 201:
            print("Заказ успешно создан")
        else:
            print(f"Ошибка при создании заказа: {response.status_code}, {response.text}")


async def main():
    async for session in get_async_session():
        available_item_ids = await get_items(session)
        await create_orders(1000, available_item_ids)


if __name__ == "__main__":
    asyncio.run(main())
