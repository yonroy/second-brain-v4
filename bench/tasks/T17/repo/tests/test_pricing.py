import unittest
from unittest import mock
from src import pricing


class TestX(unittest.TestCase):
    def test_get_price(self):
        with mock.patch("src.supplier.fetch_price", return_value=100):
            self.assertEqual(pricing.get_price("A"), 100)


if __name__ == "__main__":
    unittest.main()
