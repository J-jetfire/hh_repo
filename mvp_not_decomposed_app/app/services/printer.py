from datetime import datetime, timedelta

import pytz
from escpos.printer import Network


def connect_printer(printer_id):
    if printer_id == 1:
        printer_ip = "37.113.130.174"
        x = Network(printer_ip, port=6001)
    else:
        printer_ip = "37.113.130.174"
        x = Network(printer_ip, port=6002)
    return x


def generate_receipt_image(order_json, store_name, x):
    try:
        # Extracting information from order_json
        order_number = order_json["order_number"]
        now = datetime.now()
        target_timezone = pytz.timezone('Etc/GMT-5')
        adjusted_time = now.astimezone(target_timezone) + timedelta(hours=5)
        date_time = adjusted_time.strftime("%d.%m.%Y  ---  %H:%M")

        items = order_json["items"]
        level = order_json["level"]
        order_contacts = order_json["contacts"]
        index_of_slash = order_contacts.find('/')
        phone_number = order_contacts[index_of_slash + 2:].strip()

        x.set(font="b")
        # Adding store name
        x.text(f'{store_name}\n')
        x.text('********************************************************\n')
        x.text(f'Номер заказа: {order_number}\n')
        level_text = f'Этаж: {level}'
        x.text(f'Время заказа: {date_time}             {level_text}\n')
        x.text('********************************************************\n')
        x.text('ЗАКАЗ:\n')

        for item in items:
            x.text(f'- {item["title"]}  x {item["amount"]}\n')

        x.text('********************************************************\n')

        # Adding total amount
        total = order_json["total"]
        x.text(f'ИТОГО: {total} руб.')
        x.text('********************************************************\n')
        x.text(f'Контакт: {phone_number}\n')
        x.cut()
        x.close()
        return True
    except Exception as e:
        print(f'Error: {str(e)}')
    return False


def print_receipt(order):
    store_name = "ФУДКОРТ ТРАКТОР"
    level = order["level"]
    try:
        x = connect_printer(level)
        receipt = generate_receipt_image(order, store_name, x)
        if not receipt:
            print('error while trying to print')
            return None
    except:
        print('printer connection error')
        return None
    return receipt
