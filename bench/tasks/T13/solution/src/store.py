import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, price INTEGER)")
