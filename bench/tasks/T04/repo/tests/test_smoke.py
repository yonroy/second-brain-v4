import unittest



class TestX(unittest.TestCase):
    def test_import(self):
        import src.db  # noqa: F401


if __name__ == "__main__":
    unittest.main()
