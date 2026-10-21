import unittest
from src.customers import sort_customers


class TestX(unittest.TestCase):
    def test_vietnamese_order(self):
        self.assertEqual(sort_customers(["Bình", "Đức", "An", "Em", "Dũng"]),
                         ["An", "Bình", "Dũng", "Đức", "Em"])


if __name__ == "__main__":
    unittest.main()
