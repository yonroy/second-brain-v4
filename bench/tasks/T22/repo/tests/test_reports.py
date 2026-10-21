import unittest
from datetime import date
from src.reports import daily_totals


class TestX(unittest.TestCase):
    def test_daily(self):
        self.assertEqual(daily_totals([{"day": date(2026, 1, 5), "amount": 3}]), {"2026-01-05": 3})


if __name__ == "__main__":
    unittest.main()
