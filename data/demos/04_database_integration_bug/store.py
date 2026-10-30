import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "demo.sqlite"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DB_PATH.unlink(missing_ok=True)
    connection = connect()
    connection.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    connection.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    connection.commit()
    connection.close()


def get_user_name(user_id: int) -> str | None:
    connection = connect()
    try:
        row = connection.execute(
            "SELECT name FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return None if row is None else str(row["name"])
    finally:
        connection.close()
