import unittest
from src.wallet import withdraw


class TestX(unittest.TestCase):
    def test_withdraw(self):
        w = {"a": 100}
        withdraw(w, "a", 30)
        self.assertEqual(w["a"], 70)


if __name__ == "__main__":
    unittest.main()
