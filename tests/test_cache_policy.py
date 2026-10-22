import unittest

from cache_policy import should_cache_report


class CachePolicyTests(unittest.TestCase):
    def test_full_analysis_can_be_cached(self):
        self.assertTrue(should_cache_report(False))

    def test_smoke_test_does_not_overwrite_full_report(self):
        self.assertFalse(should_cache_report(True))

    def test_invalid_flag_fails_closed(self):
        with self.assertRaises(TypeError):
            should_cache_report(None)


if __name__ == "__main__":
    unittest.main()
