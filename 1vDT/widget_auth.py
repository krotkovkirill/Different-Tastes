import hashlib
import re
import secrets
import time

import database as db

CONNECTION_TTL = 90 * 24 * 60 * 60


def create_connection(user_id):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    db.save_widget_token(hashlib.sha256(token.encode()).hexdigest(), user_id, now + CONNECTION_TTL, now)
    return token


def connection_user(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    return db.get_widget_user(hashlib.sha256(token.encode()).hexdigest(), int(time.time()))


def revoke_connections(user_id):
    db.revoke_widget_tokens(user_id)
