import unittest
from src.phone import register


class TestX(unittest.TestCase):
    def test_register(self):
        self.assertEqual(register("0901234567")["phone"], "0901234567")


if __name__ == "__main__":
    unittest.main()
