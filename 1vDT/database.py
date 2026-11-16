import os
import sqlite3
from time import time_ns
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(os.environ.get("DT_DATA_DIR", Path(__file__).resolve().parent / "data")).expanduser().resolve()
DB_PATH = DATA_DIR / "different_tastes.db"


def connect_db():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def transaction():
    connection = connect_db()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with transaction() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                avatar_path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                photo_path TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment TEXT NOT NULL DEFAULT '' CHECK (length(comment) <= 30),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS friendships (
                id INTEGER PRIMARY KEY,
                sender_id INTEGER NOT NULL REFERENCES users(id),
                recipient_id INTEGER NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (sender_id != recipient_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS friendships_pair
                ON friendships (min(sender_id, recipient_id), max(sender_id, recipient_id));
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS widget_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                username TEXT PRIMARY KEY,
                failures INTEGER NOT NULL,
                first_failure INTEGER NOT NULL,
                blocked_until INTEGER NOT NULL DEFAULT 0
            );
        """)
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        obsolete = user_columns & {"display_name", "created_at"}
        if obsolete:
            backup_dir = DATA_DIR / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup = sqlite3.connect(backup_dir / f"before-simple-auth-{time_ns()}.db")
            try:
                connection.backup(backup)
            finally:
                backup.close()
            for column in sorted(obsolete):
                connection.execute(f"ALTER TABLE users DROP COLUMN {column}")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(posts)")}
        if "user_id" not in columns:
            connection.execute("ALTER TABLE posts ADD COLUMN user_id INTEGER REFERENCES users(id)")
        connection.execute("CREATE INDEX IF NOT EXISTS posts_author ON posts(user_id, id DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at)")


def save_post(photo_path, rating, comment, user_id):
    if user_id is None:
        raise ValueError("Нужен автор публикации")
    if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("Выбери оценку от 1 до 5")
    comment = comment.strip()
    if len(comment) > 30:
        raise ValueError("Отзыв — не более 30 символов")
    with transaction() as connection:
        cursor = connection.execute(
            "INSERT INTO posts (photo_path, rating, comment, user_id) VALUES (?, ?, ?, ?)",
            (str(photo_path), rating, comment, user_id),
        )
        return cursor.lastrowid


def get_posts(user_id):
    with transaction() as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM posts WHERE user_id = ? ORDER BY id DESC", (user_id,)
        )]


def get_feed(user_id, limit=12, before_id=None, own_only=False):
    limit = max(1, min(int(limit), 50))
    with transaction() as connection:
        rows = connection.execute("""
            SELECT p.id, p.user_id, p.photo_path, p.rating, p.comment, p.created_at,
                   u.username, profile.avatar_path
            FROM posts AS p JOIN users AS u ON u.id = p.user_id
            LEFT JOIN profiles AS profile ON profile.user_id = u.id
            WHERE (? IS NULL OR p.id < ?)
              AND (p.user_id = ? OR (? = 0 AND EXISTS (
                  SELECT 1 FROM friendships AS f
                  WHERE f.status = 'accepted' AND (
                      (f.sender_id = ? AND f.recipient_id = p.user_id)
                      OR (f.recipient_id = ? AND f.sender_id = p.user_id)
                  )
              )))
            ORDER BY p.id DESC LIMIT ?
        """, (before_id, before_id, user_id, int(own_only), user_id, user_id, limit)).fetchall()
        return [dict(row) for row in rows]


def delete_post(post_id, user_id):
    with transaction() as connection:
        row = connection.execute(
            "DELETE FROM posts WHERE id = ? AND user_id = ? RETURNING photo_path",
            (post_id, user_id),
        ).fetchone()
        return row[0] if row else None


def update_post(post_id, rating, comment, user_id):
    if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("Выбери оценку от 1 до 5")
    comment = comment.strip()
    if len(comment) > 30:
        raise ValueError("Отзыв — не более 30 символов")
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE posts SET rating = ?, comment = ? WHERE id = ? AND user_id = ?",
            (rating, comment, post_id, user_id),
        )
        return cursor.rowcount > 0


def get_user_by_username(username):
    with transaction() as connection:
        row = connection.execute("SELECT u.*, p.avatar_path FROM users AS u LEFT JOIN profiles AS p ON p.user_id=u.id WHERE u.username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user(user_id):
    with transaction() as connection:
        row = connection.execute("SELECT u.*, p.avatar_path FROM users AS u LEFT JOIN profiles AS p ON p.user_id=u.id WHERE u.id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(username, password_hash):
    with transaction() as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        return cursor.lastrowid


def set_avatar(user_id, avatar_path):
    with transaction() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT avatar_path FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        connection.execute(
            "INSERT INTO profiles(user_id, avatar_path) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET avatar_path=excluded.avatar_path",
            (user_id, avatar_path),
        )
        return row[0] if row else None


def update_password(user_id, expected_hash, new_hash):
    with transaction() as connection:
        changed = connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ? AND password_hash = ?",
            (new_hash, user_id, expected_hash),
        ).rowcount > 0
        if changed:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM widget_tokens WHERE user_id = ?", (user_id,))
        return changed


def get_stats(user_id):
    with transaction() as connection:
        posts = connection.execute("SELECT count(*) FROM posts WHERE user_id = ?", (user_id,)).fetchone()[0]
        friends = connection.execute(
            "SELECT count(*) FROM friendships WHERE status = 'accepted' AND (sender_id = ? OR recipient_id = ?)",
            (user_id, user_id),
        ).fetchone()[0]
        return {"posts": posts, "friends": friends}


def find_user(username, current_user_id):
    with transaction() as connection:
        nickname = username.strip().lower()
        row = connection.execute(
            "SELECT u.id, u.username, p.avatar_path FROM users AS u LEFT JOIN profiles AS p ON p.user_id=u.id WHERE u.username = ? AND u.id != ?",
            (nickname, current_user_id),
        ).fetchone()
        if row is None and nickname.startswith("@"):
            row = connection.execute(
                "SELECT u.id, u.username, p.avatar_path FROM users AS u LEFT JOIN profiles AS p ON p.user_id=u.id WHERE u.username = ? AND u.id != ?",
                (nickname[1:], current_user_id),
            ).fetchone()
        return dict(row) if row else None


def send_friend_request(sender_id, recipient_id):
    if sender_id == recipient_id:
        raise ValueError("Нельзя добавить себя в друзья")
    try:
        with transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO friendships (sender_id, recipient_id) VALUES (?, ?)", (sender_id, recipient_id)
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise ValueError("Заявка уже существует или вы уже друзья") from error
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
            raise ValueError("Пользователь не найден") from error
        raise


def get_friendships(user_id):
    with transaction() as connection:
        rows = connection.execute("""
            SELECT f.id, f.sender_id, f.recipient_id, f.status,
                   u.id AS user_id, u.username, profile.avatar_path
            FROM friendships AS f
            JOIN users AS u ON u.id = CASE WHEN f.sender_id = ? THEN f.recipient_id ELSE f.sender_id END
            LEFT JOIN profiles AS profile ON profile.user_id = u.id
            WHERE f.sender_id = ? OR f.recipient_id = ? ORDER BY f.id DESC
        """, (user_id, user_id, user_id)).fetchall()
        return [dict(row) for row in rows]


def respond_friend_request(request_id, user_id, accept):
    with transaction() as connection:
        query = (
            "UPDATE friendships SET status = 'accepted' WHERE id = ? AND recipient_id = ? AND status = 'pending'"
            if accept else "DELETE FROM friendships WHERE id = ? AND recipient_id = ? AND status = 'pending'"
        )
        return connection.execute(query, (request_id, user_id)).rowcount > 0


def remove_friendship(request_id, user_id):
    with transaction() as connection:
        return connection.execute("""
            DELETE FROM friendships WHERE id = ? AND (
                (status = 'accepted' AND (sender_id = ? OR recipient_id = ?))
                OR (status = 'pending' AND sender_id = ?)
            )
        """, (request_id, user_id, user_id, user_id)).rowcount > 0


def save_session(token_hash, user_id, expires_at, now):
    with transaction() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, expires_at),
        )


def get_session_user(token_hash, now):
    with transaction() as connection:
        row = connection.execute("""
            SELECT u.id, u.username, profile.avatar_path
            FROM sessions AS s JOIN users AS u ON u.id = s.user_id
            LEFT JOIN profiles AS profile ON profile.user_id = u.id
            WHERE s.token_hash = ? AND s.expires_at > ?
        """, (token_hash, now)).fetchone()
        return dict(row) if row else None


def delete_session(token_hash):
    with transaction() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def login_blocked_until(username):
    with transaction() as connection:
        row = connection.execute("SELECT blocked_until FROM login_attempts WHERE username = ?", (username,)).fetchone()
        return row[0] if row else 0


def record_login_failure(username, now):
    with transaction() as connection:
        connection.execute("DELETE FROM login_attempts WHERE first_failure <= ? AND blocked_until <= ?", (now - 300, now))
        connection.execute("""
            INSERT INTO login_attempts(username, failures, first_failure) VALUES (?, 1, ?)
            ON CONFLICT(username) DO UPDATE SET failures = failures + 1
        """, (username, now))
        connection.execute("UPDATE login_attempts SET blocked_until = ? WHERE username = ? AND failures >= 5", (now + 300, username))


def clear_login_failures(username):
    with transaction() as connection:
        connection.execute("DELETE FROM login_attempts WHERE username = ?", (username,))


if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")


def save_widget_token(token_hash, user_id, expires_at, now):
    with transaction() as connection:
        connection.execute("DELETE FROM widget_tokens WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO widget_tokens(token_hash,user_id,expires_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET token_hash=excluded.token_hash, expires_at=excluded.expires_at",
            (token_hash, user_id, expires_at),
        )


def get_widget_user(token_hash, now):
    with transaction() as connection:
        row = connection.execute(
            "SELECT u.id FROM widget_tokens AS t JOIN users AS u ON u.id=t.user_id "
            "WHERE t.token_hash=? AND t.expires_at>?", (token_hash, now),
        ).fetchone()
        return row["id"] if row else None


def revoke_widget_tokens(user_id):
    with transaction() as connection:
        connection.execute("DELETE FROM widget_tokens WHERE user_id=?", (user_id,))
