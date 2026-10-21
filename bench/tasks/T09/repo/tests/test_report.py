import unittest
from src.report import rows


class TestX(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(len(rows()), 3)


if __name__ == "__main__":
    unittest.main()
