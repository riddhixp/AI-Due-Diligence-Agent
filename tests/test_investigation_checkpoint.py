import unittest
from investigation_checkpoint import create_checkpoint, inspect_checkpoint, document_fingerprint


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b"%PDF-1.4 synthetic"
        self.checkpoint = create_checkpoint(
            document_fingerprint(self.pdf),
            {"revenue_current": 130}, 1, 0, None,
            ["read_page", "submit_financial_data"],
        )

    def test_same_pdf_matches_but_cannot_claim_resume(self):
        result = inspect_checkpoint(self.checkpoint, self.pdf)
        self.assertTrue(result["compatible"])
        self.assertFalse(result["can_resume"])
        self.assertEqual(result["reason"], "MODEL_CONVERSATION_NOT_SAVED")

    def test_changed_pdf_rejected(self):
        result = inspect_checkpoint(self.checkpoint, b"other PDF")
        self.assertFalse(result["compatible"])
        self.assertEqual(result["reason"], "DOCUMENT_MISMATCH")

    def test_preserves_submission_without_mutation(self):
        self.assertEqual(self.checkpoint["financial_data"]["revenue_current"], 130)
        self.assertEqual(self.checkpoint["submission_count"], 1)

    def test_invalid_counters_rejected(self):
        with self.assertRaises(ValueError):
            create_checkpoint(document_fingerprint(self.pdf), {}, 1, 2, None, [])

    def test_unsupported_version_rejected(self):
        self.checkpoint["version"] = 999
        self.assertFalse(inspect_checkpoint(self.checkpoint, self.pdf)["compatible"])


if __name__ == "__main__":
    unittest.main()
