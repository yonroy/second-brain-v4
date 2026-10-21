import unittest
from src.cart import total


class TestX(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total([{"price": 100, "cat": "food"}]), 105)


if __name__ == "__main__":
    unittest.main()
