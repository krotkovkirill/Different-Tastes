import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "different_tastes.db"

def init_db():
    DATA_DIR.mkdir(parents = True, exist_ok = True)
    connection = sqlite3.connect(DB_PATH)

    try:
        connection.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            photo_path TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT NOT NULL DEFAULT '' CHECK (length(comment) <= 30),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)
            """)
        connection.commit()
    finally:
        connection.close()


def save_post(photo_path, rating, comment):
    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.execute("""INSERT INTO posts (photo_path, rating, comment)
        VALUES (?, ?, ?)""",
        (str(photo_path), rating, comment))
        connection.commit()
        return cursor.lastrowid  # ID только что созданной публикации
    finally:
        connection.close()

def get_posts():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("""
        SELECT id, photo_path, rating, comment, created_at FROM posts
        ORDER BY id DESC""").fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_post(post_id):
    connection = sqlite3.connect(DB_PATH)
    try:
        row = connection.execute(
            "SELECT photo_path FROM posts WHERE id = ?",  # Находим файл по ID поста
            (post_id,),
        ).fetchone()
        if row is None:
            return None

        connection.execute(
            "DELETE FROM posts WHERE id = ?",  # Удаляем только выбранную запись
            (post_id,),
        )
        connection.commit()
        return row[0]
    finally:
        connection.close()


def update_post(post_id, rating, comment):
    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.execute(
            "UPDATE posts SET rating = ?, comment = ? WHERE id = ?",
            (rating, comment, post_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")
    print(get_posts())
