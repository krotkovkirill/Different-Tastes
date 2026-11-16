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
    if not password:
        raise ValueError("Введи пароль")


def public_user(user):
    return {key: user[key] for key in ("id", "username")}


def login_user(username, password):
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Неверный ник или пароль")
    now = int(time.time())
    if db.login_blocked_until(username) > now:
        raise ValueError("Слишком много попыток. Попробуй через 5 минут.")
    user = db.get_user_by_username(username)
    if user is None or not verify_password(user["password_hash"], password):
        db.record_login_failure(username, now)
        raise ValueError("Неверный пароль" if user is not None else "Неверный ник или пароль")
    db.clear_login_failures(username)
    return public_user(user)


def sign_in(username, password):
    username = username.strip().lower()
    if not username:
        raise ValueError("Введи ник")
    validate_password(password)
    if db.get_user_by_username(username) is not None:
        return login_user(username, password)
    try:
        user_id = db.create_user(username, hash_password(password))
        return {"id": user_id, "username": username}
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode != sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise
        return login_user(username, password)


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
