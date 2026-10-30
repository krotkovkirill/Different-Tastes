import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from database import create_user, get_user_by_username


password_hasher = PasswordHasher()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def register_user(username, display_name, password):
    username = username.strip().lower()
    display_name = display_name.strip()

    if not 3 <= len(username) <= 32:
        raise ValueError("Логин должен содержать от 3 до 32 символов")
    if not 1 <= len(display_name) <= 50:
        raise ValueError("Имя должно содержать от 1 до 50 символов")
    if not 3 <= len(password) <= 128:
        raise ValueError("Пароль должен содержать от 3 до 128 символов")

    password_hash = hash_password(password)
    try:
        user_id = create_user(username, display_name, password_hash)
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise ValueError("Этот логин уже занят") from error
        raise

    return {
        "id": user_id,
        "username": username,
        "display_name": display_name,
    }


def login_user(username, password):
    username = username.strip().lower()
    user = get_user_by_username(username)

    if user is None:
        raise ValueError("Неверный логин или пароль")

    if not verify_password(user["password_hash"], password):
        raise ValueError("Неверный логин или пароль")

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    }


if __name__ == "__main__":
    first = hash_password("learning-password")
    second = hash_password("learning-password")

    print(first)
    print(second)
    print(first == second)