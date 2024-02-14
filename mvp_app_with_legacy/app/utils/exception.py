from fastapi import HTTPException, status


def custom_errors(description: str, error_list: list):
    errors_dict = {"description": description,
                   "content": {"application/json": {"examples": {}}}}
    for err in error_list:
        errors_dict["content"]["application/json"]["examples"][err["msg"]] = {"summary": err["msg"], "value": err}
    return errors_dict

credentials_admin_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail={"msg": "Permission denied"},
    headers={"WWW-Authenticate": "Bearer"},
)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"msg": "Could not validate credentials"},
    headers={"WWW-Authenticate": "Bearer"},
)

not_authenticated_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"msg": "Not authenticated"},
    headers={"WWW-Authenticate": "Bearer"},
)

unexpected_error = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"msg": "Непредвиденная ошибка, попробуйте позже"}
)

user_not_exist = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"msg": "Пользователя не существует"}
)

user_exists = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={"msg": "Номер привязан к другому пользователю"}
)
