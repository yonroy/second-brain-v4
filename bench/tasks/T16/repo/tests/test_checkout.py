import unittest
from src.cart import new_cart, add_item
from src.checkout import checkout


class TestX(unittest.TestCase):
    def test_total(self):
        c = new_cart()
        add_item(c, "x", 100, 2)
        self.assertEqual(checkout(c)["total"], 200)


if __name__ == "__main__":
    unittest.main()
