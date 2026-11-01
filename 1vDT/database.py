import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "different_tastes.db"

def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    DATA_DIR.mkdir(parents = True, exist_ok = True)
    connection = connect_db()

    try:
        connection.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            photo_path TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT NOT NULL DEFAULT '' CHECK (length(comment) <= 30),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS friendships (
                id INTEGER PRIMARY KEY,
                sender_id INTEGER NOT NULL REFERENCES users(id),
                recipient_id INTEGER NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (sender_id != recipient_id)
            )
        """)
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS friendships_pair
            ON friendships (min(sender_id, recipient_id), max(sender_id, recipient_id))
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(posts)")}
        if "user_id" not in columns:
            connection.execute("ALTER TABLE posts ADD COLUMN user_id INTEGER REFERENCES users(id)")
        connection.commit()
    finally:
        connection.close()


def save_post(photo_path, rating, comment, user_id):
    if user_id is None:
        raise ValueError("Нужен автор публикации")
    connection = connect_db()
    try:
        cursor = connection.execute("""INSERT INTO posts (photo_path, rating, comment, user_id)
        VALUES (?, ?, ?, ?)""",
        (str(photo_path), rating, comment, user_id))
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()

def get_posts(user_id):
    connection = connect_db()
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("""
        SELECT id, user_id, photo_path, rating, comment, created_at FROM posts
        WHERE user_id = ?
        ORDER BY id DESC""", (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_feed(user_id):
    connection = connect_db()
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("""
            SELECT p.id, p.user_id, p.photo_path, p.rating, p.comment, p.created_at,
                   u.username, u.display_name
            FROM posts AS p
            JOIN users AS u ON u.id = p.user_id
            WHERE p.user_id = ? OR EXISTS (
                SELECT 1 FROM friendships AS f
                WHERE f.status = 'accepted' AND (
                    (f.sender_id = ? AND f.recipient_id = p.user_id)
                    OR (f.recipient_id = ? AND f.sender_id = p.user_id)
                )
            )
            ORDER BY p.id DESC
        """, (user_id, user_id, user_id)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()

def created_user(username, display_name, password_hash):
    connection = connect_db()
    try: 
        cursor = connection.execute(
            """
            INSERT INTO users (username, display_name, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, display_name, password_hash)
        ) 
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()

def delete_post(post_id, user_id):
    connection = connect_db()
    try:
        row = connection.execute(
            "DELETE FROM posts WHERE id = ? AND user_id = ? RETURNING photo_path",
            (post_id, user_id),
        ).fetchone()
        connection.commit()
        return row[0] if row else None
    finally:
        connection.close()


def update_post(post_id, rating, comment, user_id):
    connection = connect_db()
    try:
        cursor = connection.execute(
            "UPDATE posts SET rating = ?, comment = ? WHERE id = ? AND user_id = ?",
            (rating, comment, post_id, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def get_user_by_username(username):
    connection = connect_db()
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            """
            SELECT id, username, display_name, password_hash
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        return dict(row) if row else None
    finally:
        connection.close()


def create_user(username, display_name, password_hash):
    connection = connect_db()
    try:
        cursor = connection.execute(
            "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
            (username, display_name, password_hash),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def find_user(username, current_user_id):
    connection = connect_db()
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT id, username, display_name FROM users WHERE username = ? AND id != ?",
            (username.strip().lower(), current_user_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def send_friend_request(sender_id, recipient_id):
    if sender_id == recipient_id:
        raise ValueError("Нельзя добавить себя в друзья")
    connection = connect_db()
    try:
        cursor = connection.execute(
            "INSERT INTO friendships (sender_id, recipient_id) VALUES (?, ?)",
            (sender_id, recipient_id),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise ValueError("Заявка уже существует или вы уже друзья") from error
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
            raise ValueError("Пользователь не найден") from error
        raise
    finally:
        connection.close()


def get_friendships(user_id):
    connection = connect_db()
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("""
            SELECT f.id, f.sender_id, f.recipient_id, f.status,
                   u.id AS user_id, u.username, u.display_name
            FROM friendships AS f
            JOIN users AS u ON u.id = CASE
                WHEN f.sender_id = ? THEN f.recipient_id ELSE f.sender_id END
            WHERE f.sender_id = ? OR f.recipient_id = ?
            ORDER BY f.id DESC
        """, (user_id, user_id, user_id)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def respond_friend_request(request_id, user_id, accept):
    connection = connect_db()
    try:
        if accept:
            cursor = connection.execute(
                "UPDATE friendships SET status = 'accepted' WHERE id = ? AND recipient_id = ? AND status = 'pending'",
                (request_id, user_id),
            )
        else:
            cursor = connection.execute(
                "DELETE FROM friendships WHERE id = ? AND recipient_id = ? AND status = 'pending'",
                (request_id, user_id),
            )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def remove_friendship(request_id, user_id):
    connection = connect_db()
    try:
        cursor = connection.execute("""
            DELETE FROM friendships WHERE id = ? AND (
                (status = 'accepted' AND (sender_id = ? OR recipient_id = ?))
                OR (status = 'pending' AND sender_id = ?)
            )
        """, (request_id, user_id, user_id, user_id))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")
