import unittest

from verification_notice import final_verification_notice


class FinalVerificationNoticeTests(unittest.TestCase):
    def test_missing_financial_data_is_unverified(self):
        level, message = final_verification_notice({}, None)
        self.assertEqual(level, "warning")
        self.assertIn("unverified", message)

    def test_review_unavailable_is_warning(self):
        level, _ = final_verification_notice({"company": "A"}, None)
        self.assertEqual(level, "warning")

    def test_failed_source_review_is_warning(self):
        level, message = final_verification_notice(
            {"company": "A"},
            {"status": "NEEDS_REVIEW", "metadata_issues": ["currency missing"]},
        )
        self.assertEqual(level, "warning")
        self.assertIn("currency missing", message)

    def test_preliminary_pass_never_claims_audit(self):
        level, message = final_verification_notice(
            {"company": "A"},
            {"status": "PRELIMINARY_CHECKS_PASSED"},
        )
        self.assertEqual(level, "info")
        self.assertIn("not a full financial audit", message)


if __name__ == "__main__":
    unittest.main()
