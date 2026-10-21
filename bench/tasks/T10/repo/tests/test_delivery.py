import unittest
from datetime import datetime, timezone
from src.delivery import eta


class TestX(unittest.TestCase):
    def test_eta(self):
        t = datetime(2026, 3, 5, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(eta(t, 2).hour, 22)


if __name__ == "__main__":
    unittest.main()
