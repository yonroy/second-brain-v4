import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, total INTEGER)")


def load_orders(conn, rows):
    conn.executemany(
        "INSERT INTO orders(order_id, total) VALUES (:order_id, :total) "
        "ON CONFLICT(order_id) DO UPDATE SET total = excluded.total", rows)
    conn.commit()
