import unittest

from investigation_control import submission_block_reason


class SubmissionControlTests(unittest.TestCase):
    def test_initial_submission_permitted(self):
        self.assertIsNone(submission_block_reason(0, 0, None))

    def test_correction_requires_review(self):
        self.assertIn(
            "REVIEW_REQUIRED",
            submission_block_reason(1, 0, None),
        )

    def test_correction_requires_failed_review(self):
        self.assertIn(
            "CORRECTION_NOT_PERMITTED",
            submission_block_reason(1, 1, "PRELIMINARY_CHECKS_PASSED"),
        )

    def test_correction_after_failed_review_permitted(self):
        self.assertIsNone(submission_block_reason(1, 1, "NEEDS_REVIEW"))

    def test_third_submission_blocked(self):
        self.assertIn(
            "SUBMISSION_LIMIT_REACHED",
            submission_block_reason(2, 2, "NEEDS_REVIEW"),
        )


if __name__ == "__main__":
    unittest.main()
