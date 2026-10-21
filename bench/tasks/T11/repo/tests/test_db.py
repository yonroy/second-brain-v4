import unittest
from src import db


class TestX(unittest.TestCase):
    def setUp(self):
        with db.connect() as c:
            c.execute("DELETE FROM customers")

    def test_sorted(self):
        for n in ("Charlie", "alice", "Bob"):
            db.add_customer(n)
        self.assertEqual(db.list_customers(), ["alice", "Bob", "Charlie"])


if __name__ == "__main__":
    unittest.main()
