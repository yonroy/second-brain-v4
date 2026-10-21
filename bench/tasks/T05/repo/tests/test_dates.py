import unittest
from datetime import date
from src.dates import parse_date


class TestX(unittest.TestCase):
    def test_slash(self):
        self.assertEqual(parse_date("05/03/2026"), date(2026, 3, 5))

    def test_dash(self):
        self.assertEqual(parse_date("06-03-2026"), date(2026, 3, 6))


if __name__ == "__main__":
    unittest.main()
