import os
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent


def db_path() -> pathlib.Path:
    name = "test.db" if os.environ.get("APP_ENV") == "test" else "prod.db"
    return ROOT / "data" / name


def connect():
    c = sqlite3.connect(db_path())
    c.execute("CREATE TABLE IF NOT EXISTS customers (name TEXT)")
    return c


def add_customer(name):
    with connect() as c:
        c.execute("INSERT INTO customers(name) VALUES (?)", (name,))


def list_customers():
    with connect() as c:
        return sorted((r[0] for r in c.execute("SELECT name FROM customers")), key=str.casefold)
