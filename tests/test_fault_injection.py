import unittest
from fault_injection import inject_first_submission_error


class FaultInjectionTests(unittest.TestCase):
    def setUp(self):
        self.submission = {"revenue_current": 120, "revenue_previous": 100}
        self.synthetic = ["SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY"]

    def test_first_submission_injected_on_synthetic_fixture(self):
        result, injected = inject_first_submission_error(
            self.submission, self.synthetic, enabled=True, accepted_count=0)
        self.assertTrue(injected)
        self.assertEqual(result["revenue_current"], 130)
        self.assertEqual(self.submission["revenue_current"], 120)

    def test_real_filing_never_changed(self):
        result, injected = inject_first_submission_error(
            self.submission, ["Real filing"], enabled=True, accepted_count=0)
        self.assertFalse(injected)
        self.assertEqual(result, self.submission)

    def test_opt_in_required(self):
        _, injected = inject_first_submission_error(
            self.submission, self.synthetic, enabled=False, accepted_count=0)
        self.assertFalse(injected)

    def test_second_submission_never_changed(self):
        _, injected = inject_first_submission_error(
            self.submission, self.synthetic, enabled=True, accepted_count=1)
        self.assertFalse(injected)

    def test_unsupported_initial_value_not_changed(self):
        result, injected = inject_first_submission_error(
            {"revenue_current": 140}, self.synthetic,
            enabled=True, accepted_count=0)
        self.assertFalse(injected)
        self.assertEqual(result["revenue_current"], 140)


if __name__ == "__main__":
    unittest.main()
