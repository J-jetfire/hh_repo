# import bcrypt


# def hash_password(password: str) -> bytes:
#     pw = bytes(password, "utf-8")
#     salt = bcrypt.gensalt()
#     return bcrypt.hashpw(pw, salt)


def check_password(password: str, password_in_db: str) -> bool:
    # password_bytes = bytes(password, "utf-8")
    # return bcrypt.checkpw(password_bytes, password_in_db)
    # print('password_in_db', password_in_db)
    return password == password_in_db
