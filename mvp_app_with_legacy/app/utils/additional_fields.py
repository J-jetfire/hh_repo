from app.utils.quarter import get_yearly_quarters
from app.schemas.car import Car
from app.crud import car as car_crud


def validate_fields(field, data, db):
    catalog_data = field # полученные данные раздела каталога по идентификатору
    validate_data = data # полученные данные из запроса
    invalid_data = {'error': "", 'aliases': {}}  # массив для записи ошибок

    if not validate_data: # если запрос пустой, то записываем ошибку и возвращаем ее, без продолжения
        invalid_data['error'] = "В запросе не найдены данные"
        return invalid_data

    for key, value in validate_data.items(): # для каждого alias-ключа и его значения| проходим по данным из запроса
        # key = значение alias, value = данные из запроса по текущему alias-у
        # Пример =>   key  : value
        # ========> "model": "BMW"

        # получем одно доп.поле совпадающее с alias-ом из запроса
        catalog_item = [catalog_item for catalog_item in catalog_data['additional_fields'] if
                        catalog_item.get('alias') == key]
        # print('catalog_item', catalog_item)
        # если совпадений нет, то пишем ошибку и пропускаем этот круг цикла
        if not catalog_item:
            invalid_data['aliases'][key] = "Ошибка входных данных. В каталоге нет такого поля"
            continue

        required = catalog_item[0]['required'] # обязательное ли к заполнению поле - значение true/false
        item_type = catalog_item[0]['data']['type'] # тип поля в каталоге

        item_properties = catalog_item[0]['data']['properties'] # данные properties в каталоге для этого поля

        # Валидируем все доп.поля по типу
        if item_type == 'select':
            validate_select_field(item_properties['options'], required, invalid_data, key, value)

        elif item_type == 'checkboxes':
            validate_checkboxes_field(item_properties['checks'], required, invalid_data, key, value)

        elif item_type == 'color':
            validate_color_field(item_properties['colors'], required, invalid_data, key, value)

        elif item_type == 'text':
            validate_text_field(required, invalid_data, key, value)

        elif item_type == 'number':
            validate_number_field(item_properties, required, invalid_data, key, value)

        elif item_type == 'checkbox':
            validate_checkbox_field(invalid_data, key, value)

        elif item_type == 'select_request':
            validate_request_field(validate_data, db, item_properties, required, invalid_data, key, value)

    return invalid_data


def validate_select_field(validate_list, required, invalid_data, key, value):
    if not isinstance(value, str):
        invalid_data['aliases'][key] = "Неправильный тип данных"
    elif not value and required:
        invalid_data['aliases'][key] = "Обязательное поле"
    elif value and value not in validate_list:
        invalid_data['aliases'][key] = "Недопустимое значение"


def validate_checkboxes_field(validate_list, required, invalid_data, key, value):
    if not isinstance(value, list):
        invalid_data['aliases'][key] = "Неправильный тип данных"
    elif not value and required:
        invalid_data['aliases'][key] = "Обязательное поле"
    elif value and not all(check in validate_list for check in value):
        invalid_data['aliases'][key] = "Недопустимое значение"


def validate_color_field(validate_list, required, invalid_data, key, value):
    validate_list = [color['name'] for color in validate_list]

    if not isinstance(value, str):
        invalid_data['aliases'][key] = "Неправильный тип данных"
    elif not value and required:
        invalid_data['aliases'][key] = "Обязательное поле"
    elif value and value not in validate_list:
        invalid_data['aliases'][key] = "Недопустимое значение"


def validate_text_field(required, invalid_data, key, value):
    if not isinstance(value, str):
        invalid_data['aliases'][key] = "Неправильный тип данных"
    elif not value and required:
        invalid_data['aliases'][key] = "Обязательное поле"
    elif len(value) > 255:
        invalid_data['aliases'][key] = "Превышен лимит симоволов: максимум 255"


def validate_number_field(validate_list, required, invalid_data, key, value):
    number_type = validate_list['type']
    min_value = validate_list['min']
    max_value = validate_list['max']

    if not value and required:
        invalid_data['aliases'][key] = "Обязательное поле"
        return
    elif value:
        try:
            if number_type == 'int':
                value = int(value)
            elif number_type == 'float':
                value = float(value)
            else:
                invalid_data['aliases'][key] = "Неправильный тип данных"
            if value < min_value or value > max_value:
                invalid_data['aliases'][key] = f"Введите значение от {min_value} до {max_value}"
        except ValueError:
            invalid_data['aliases'][key] = "Неправильный тип данных"


def validate_checkbox_field(invalid_data, key, value):
    if not isinstance(value, bool):
        invalid_data['aliases'][key] = "Неправильный тип данных"


def validate_request_field(validate_data, db, item_properties, required, invalid_data, key, value):
    if not isinstance(value, str):
        invalid_data['aliases'][key] = "Неправильный тип данных"
    elif not value and required:
        invalid_data['aliases'][key] = "Обязательное поле"
        return

    item_url = item_properties['url']

    if item_url == 'quarter':
        item_quarters = get_yearly_quarters()
        if value not in item_quarters['values']:
            invalid_data['aliases'][key] = "Недопустимое значение"

    if item_url == 'car':
        item_dependencies = item_properties['dependencies']  # все зависимости значений для поля
        car_data = {}
        if not item_dependencies:
            car = Car(**car_data)
            suggestion = car_crud.car_suggestion(db=db, car=car)
            suggestion = suggestion['values']
            if value not in suggestion:
                invalid_data['aliases'][key] = "Недопустимое значение"
        else:
            for car_key, car_value in validate_data.items():
                if car_key in item_dependencies:
                    car_data[car_key] = car_value

            car = Car(**car_data)

            try:
                suggestion = car_crud.car_suggestion(db=db, car=car)
                suggestion = set(map(str, suggestion['values']))
                if value not in suggestion:
                    invalid_data['aliases'][key] = "Недопустимое значение"
            except Exception:
                invalid_data['aliases'][key] = "Недопустимое значение"

