import json

from fastapi import HTTPException
from requests import request

from app.core.config import settings
from app.utils.exception import unexpected_error


def call(phone: str):
    url, api_key = settings.VOICEPASSWORD_API_URL, settings.VOICEPASSWORD_API_KEY
    payload = json.dumps({
        "number": phone,
    })
    headers = {
        'Authorization': api_key,
        'Accept-Charset': 'utf-8',
        'Content-Type': 'application/json'
    }
    response = request("POST", url, headers=headers, data=payload)
    return response.json()


def call_telefon_ip(phone: str):
    url = settings.TELEFON_IP_API_URL
    phone_str = str(phone)
    phone_str = phone_str.lstrip('+') # Удаление первого символа "+", если есть
    phone_str = phone_str.replace(' ', '') # Удаление пробелов
    # # Если длина строки равна 11 и начинается с "7", заменяем "7" на "8"
    if len(phone_str) == 11 and phone_str.startswith('7'):
        phone_str = '8' + phone_str[1:]
    # phone = +79XXXXXXXXX => 89XXXXXXXXX

    url += phone_str
    # print('url', url)
    response = request("GET", url)
    # print('response', response.json())
    return response.json()


def error_handler(error: str):
    match error:
        case "unknown_request":
            raise HTTPException(status_code=404, detail={"msg": "Ошибочный запрос"})
        case "authorisation_failed":
            raise unexpected_error
        case "user_disabled ":
            raise unexpected_error
        case "number_is_empty":
            raise HTTPException(status_code=404, detail={"msg": "Некорректно указан номер абонента"})
        case "number_not_valid":
            raise HTTPException(status_code=404, detail={"msg": "Не удалось определить направление"})
        case "number_not_permitted":
            raise HTTPException(status_code=404, detail={"msg": "Звонки на данное направление запрещены"})
        case "number_in_spam_list":
            raise HTTPException(status_code=404, detail={"msg": "Номер занесен в СПАМ лист. Попробуйте через сутки."})
        case "does not match the format 89XXXXXXXXX or phone field is missing":
            raise HTTPException(status_code=404, detail={"msg": "Ошибочный запрос"})
        case "Unauthorized token":
            raise HTTPException(status_code=404, detail={"msg": "Ошибка авторизации"})
        case "not_enough_money":
            raise unexpected_error
        case "ani_phone_not_valid":
            raise unexpected_error
        case "code_not_valid":
            raise HTTPException(status_code=404, detail={"msg": "Некорректно указан код"})
        case "code_not_valid":
            raise HTTPException(status_code=404, detail={"msg": "Некорректно указан код"})