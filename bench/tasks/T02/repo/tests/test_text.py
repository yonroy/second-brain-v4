import unittest
from src.text import normalize_spaces


class TestX(unittest.TestCase):
    def test_normalize_spaces(self):
        self.assertEqual(normalize_spaces("  a   b "), "a b")


if __name__ == "__main__":
    unittest.main()
