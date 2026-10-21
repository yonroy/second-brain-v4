import unittest
from src.schema import connect


class TestX(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(connect().execute("SELECT COUNT(*) FROM customers").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
