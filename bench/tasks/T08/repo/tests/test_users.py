import unittest
from src.orders import order_owner
from src.reports.summary import owner_names
from src.users import get_usr


class TestX(unittest.TestCase):
    def test_get(self):
        self.assertEqual(get_usr(1)["name"], "user1")

    def test_callers(self):
        self.assertEqual(order_owner({"user_id": 2}), "user2")
        self.assertEqual(owner_names([3]), ["user3"])


if __name__ == "__main__":
    unittest.main()
