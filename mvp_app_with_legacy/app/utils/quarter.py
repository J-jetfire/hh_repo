import math
import datetime


# Функция получения кварталов
def get_yearly_quarters():
    """
    Получение кварталов для текущей даты

    Возвращает:
    - name: quarter.
    - values: Список строк со значениями кварталов.
    - completedFields: null.
    """
    yearly_quarters = []
    # Получаем текущий месяц и год
    month = datetime.datetime.utcnow().month
    year = datetime.datetime.utcnow().year
    # Вычисляем список кварталов от текущего месяца
    quarter = math.ceil(month / 3)
    yearly_quarters.append("Дом сдан")
    for i in range(quarter, 5):
        yearly_quarters.append(f"{i} квартал {year}")
    for i in range(1, 5):
        yearly_quarters.append(f"{i} квартал {year + 1}")
    yearly_quarters.append(f"{year + 2} год и позднее")

    query = [x for x in yearly_quarters]
    return {"name": "quarter", "values": query}
