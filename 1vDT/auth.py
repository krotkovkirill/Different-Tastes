import hashlib
import re
import secrets
import sqlite3
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

import database as db

password_hasher = PasswordHasher()
SESSION_TTL = 7 * 24 * 60 * 60
SESSION_STORAGE_KEY = "different_tastes.session.v1"


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError, TypeError):
        return False


def validate_password(password):
    if not 8 <= len(password) <= 128:
        raise ValueError("Пароль должен содержать от 8 до 128 символов")


def public_user(user):
    return {key: user[key] for key in ("id", "username", "display_name")}


def register_user(username, display_name, password):
    username = username.strip().lower()
    display_name = display_name.strip()
    if not re.fullmatch(r"[a-z0-9_.]{3,32}", username):
        raise ValueError("Логин: 3–32 латинские буквы, цифры, точки или подчёркивания")
    if not 1 <= len(display_name) <= 50:
        raise ValueError("Имя должно содержать от 1 до 50 символов")
    validate_password(password)
    try:
        user_id = db.create_user(username, display_name, hash_password(password))
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise ValueError("Этот логин уже занят") from error
        raise
    return {"id": user_id, "username": username, "display_name": display_name}


def login_user(username, password):
    username = username.strip().lower()
    if not username or len(username) > 128 or not password or len(password) > 128:
        raise ValueError("Неверный логин или пароль")
    now = int(time.time())
    if db.login_blocked_until(username) > now:
        raise ValueError("Слишком много попыток. Попробуй через 5 минут.")
    user = db.get_user_by_username(username)
    if user is None or not verify_password(user["password_hash"], password):
        db.record_login_failure(username, now)
        raise ValueError("Неверный логин или пароль")
    db.clear_login_failures(username)
    return public_user(user)


def change_password(user_id, current_password, new_password):
    validate_password(new_password)
    user = db.get_user(user_id)
    if user is None:
        raise ValueError("Аккаунт не найден")
    now = int(time.time())
    if db.login_blocked_until(user["username"]) > now:
        raise ValueError("Слишком много попыток. Попробуй через 5 минут.")
    if not verify_password(user["password_hash"], current_password):
        db.record_login_failure(user["username"], now)
        raise ValueError("Текущий пароль указан неверно")
    if current_password == new_password:
        raise ValueError("Новый пароль должен отличаться от текущего")
    if not db.update_password(user_id, user["password_hash"], hash_password(new_password)):
        raise ValueError("Пароль уже изменился. Войди снова.")
    db.clear_login_failures(user["username"])


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())
    db.save_session(token_hash, user_id, now + SESSION_TTL, now)
    return token


def resume_session(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    return db.get_session_user(hashlib.sha256(token.encode()).hexdigest(), int(time.time()))


def end_session(token):
    if isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        db.delete_session(hashlib.sha256(token.encode()).hexdigest())
