import unittest
from src import http


class TestX(unittest.TestCase):
    def test_get(self):
        self.assertTrue(callable(http.http_get))


if __name__ == "__main__":
    unittest.main()
