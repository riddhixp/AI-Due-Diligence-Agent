import unittest

from run_limits import permitted_turn_limit


class RunLimitTests(unittest.TestCase):
    def test_production_default(self):
        self.assertEqual(permitted_turn_limit(), 20)

    def test_bounded_smoke_test(self):
        self.assertEqual(permitted_turn_limit(8), 8)

    def test_reject_zero(self):
        with self.assertRaises(ValueError):
            permitted_turn_limit(0)

    def test_reject_excessive_limit(self):
        with self.assertRaises(ValueError):
            permitted_turn_limit(100)

    def test_reject_bool(self):
        with self.assertRaises(ValueError):
            permitted_turn_limit(True)


if __name__ == "__main__":
    unittest.main()
