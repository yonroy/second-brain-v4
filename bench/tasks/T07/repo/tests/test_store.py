import unittest
import sqlite3
from src.store import init_db


class TestX(unittest.TestCase):
    def test_init(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
