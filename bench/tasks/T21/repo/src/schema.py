import sqlite3

DDL = "CREATE TABLE customers (id INTEGER PRIMARY KEY, cust_name TEXT, spent INTEGER)"


def connect():
    c = sqlite3.connect(":memory:")
    c.execute(DDL)
    c.executemany("INSERT INTO customers(cust_name, spent) VALUES (?, ?)", [("An", 300), ("Bình", 500), ("Chi", 100)])
    return c
