from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


password_hasher = PasswordHasher()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


if __name__ == "__main__":
    first = hash_password("learning-password")
    second = hash_password("learning-password")

    print(first)
    print(second)
    print(first == second)