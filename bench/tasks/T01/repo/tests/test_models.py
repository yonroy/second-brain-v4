import unittest
from src.models import User


class TestX(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(User().name, "")


if __name__ == "__main__":
    unittest.main()
