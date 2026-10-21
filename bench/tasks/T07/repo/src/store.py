import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT, total INTEGER)")
