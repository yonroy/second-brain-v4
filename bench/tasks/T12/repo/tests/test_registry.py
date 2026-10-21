import unittest
from src.registry import dispatch


class TestX(unittest.TestCase):
    def test_dispatch(self):
        self.assertEqual(dispatch("order.created", {"id": 1}), "created:1")
        self.assertEqual(dispatch("order.paid", {"id": 2}), "paid:2")


if __name__ == "__main__":
    unittest.main()
