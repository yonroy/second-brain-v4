"""Chạy test với APP_ENV=test (DB riêng cho test)."""
import os
import sys
import unittest

os.environ["APP_ENV"] = "test"
suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
sys.exit(0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1)
