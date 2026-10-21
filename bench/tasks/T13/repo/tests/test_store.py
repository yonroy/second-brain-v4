import unittest
import sqlite3
from src.store import init_db


class TestX(unittest.TestCase):
    def test_init(self):
        c = sqlite3.connect(":memory:")
        init_db(c)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM products").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
