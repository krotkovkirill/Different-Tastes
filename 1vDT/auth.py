from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from database import get_user_by_username


password_hasher = PasswordHasher()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


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