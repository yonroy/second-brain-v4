import unittest
from src import jobs


class TestX(unittest.TestCase):
    def test_enqueue(self):
        jobs.enqueue("x", {})
        self.assertEqual(jobs.QUEUE[-1]["kind"], "x")


if __name__ == "__main__":
    unittest.main()
