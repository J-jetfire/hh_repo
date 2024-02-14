class ErrorCode:
    AUTHENTICATION_REQUIRED = "Необходима аутентификация"
    AUTHORIZATION_FAILED = "Не авторизован. У пользователя нет доступа"
    INVALID_TOKEN = "Неверный токен"
    INVALID_CREDENTIALS = "Неверные реквизиты для входа"
    USERNAME_TAKEN = "Пользователь с таким логином уже существует"
    REFRESH_TOKEN_NOT_VALID = "Неверный рефреш токен"
    REFRESH_TOKEN_REQUIRED = "Обязательно наличие рефреш токена"
