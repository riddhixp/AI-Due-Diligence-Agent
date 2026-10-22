import unittest
from copy import deepcopy
from investigation_checkpoint import create_checkpoint, document_fingerprint
from restored_continuation_demo import simulate_restored_continuation
from tests.test_investigation_scenarios import PAGES, supported_submission


class RestoredContinuationTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"fixture for offline replay"
        self.wrong = supported_submission()
        self.wrong["revenue_current"] = 130
        self.wrong["reported"]["revenue_growth"] = 30
        self.cp = create_checkpoint(
            document_fingerprint(self.pdf), self.wrong, 1, 0, None,
            ["read_page", "submit_financial_data"]
        )

    def test_restored_unreviewed_submission_is_corrected(self):
        result = simulate_restored_continuation(
            self.cp, self.pdf, PAGES, supported_submission()
        )
        self.assertEqual(result["evaluation"], "PRELIMINARY_PASS")
        self.assertEqual(result["investigation_outcome"],
                         "CORRECTION_PASSED_PRELIMINARY_CHECKS")
        self.assertFalse(result["conversation_restored"])
        self.assertEqual(result["api_calls"], 0)

    def test_different_document_rejected(self):
        with self.assertRaisesRegex(ValueError, "DOCUMENT_MISMATCH"):
            simulate_restored_continuation(
                self.cp, b"different", PAGES, supported_submission()
            )

    def test_unchanged_correction_rejected(self):
        with self.assertRaisesRegex(ValueError, "NO_CORRECTION_MADE"):
            simulate_restored_continuation(
                self.cp, self.pdf, PAGES, deepcopy(self.wrong)
            )

    def test_checkpoint_remains_unchanged(self):
        simulate_restored_continuation(
            self.cp, self.pdf, PAGES, supported_submission()
        )
        self.assertEqual(self.cp["reviewed_count"], 0)
        self.assertEqual(self.cp["tool_calls"],
                         ["read_page", "submit_financial_data"])


if __name__ == "__main__":
    unittest.main()
