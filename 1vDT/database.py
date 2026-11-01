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


if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")
