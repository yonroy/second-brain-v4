import unittest
from src.shipping.fees import shipping_fee


class TestX(unittest.TestCase):
    def test_light(self):
        self.assertEqual(shipping_fee({"kg": 1, "zone": "HN"}), 20000)


if __name__ == "__main__":
    unittest.main()
