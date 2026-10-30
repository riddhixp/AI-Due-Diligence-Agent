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

    def test_nested_figures_are_independent_snapshots(self):
        figures = {'revenue_current': 130, 'reported': {'revenue_growth': 30},
                   'source_pages': {'revenue_current': 2}}
        checkpoint = create_checkpoint(document_fingerprint(self.pdf), figures, 1, 0, None,
                                       ['read_page', 'submit_financial_data'])
        figures['reported']['revenue_growth'] = 20
        figures['source_pages']['revenue_current'] = 99
        self.assertEqual(checkpoint['financial_data']['reported']['revenue_growth'], 30)
        self.assertEqual(checkpoint['financial_data']['source_pages']['revenue_current'], 2)
        checkpoint['financial_data']['reported']['revenue_growth'] = 10
        self.assertEqual(figures['reported']['revenue_growth'], 20)

    def test_boolean_or_noninteger_versions_are_not_compatible(self):
        for value in [True, 1.0, '1', None]:
            self.checkpoint['version'] = value
            result = inspect_checkpoint(self.checkpoint, self.pdf)
            self.assertFalse(result['compatible'])
            self.assertFalse(result['can_resume'])

    def test_checkpoint_cannot_claim_saved_sdk_conversation(self):
        for value in [True, None, 0, 'false']:
            self.checkpoint['model_conversation_saved'] = value
            result = inspect_checkpoint(self.checkpoint, self.pdf)
            self.assertFalse(result['compatible'])
            self.assertEqual(result['reason'], 'INVALID_CHECKPOINT_CAPABILITIES')
            self.assertFalse(result['can_resume'])

    def test_creation_rejects_invalid_fingerprints_and_counters(self):
        for value in [None, '', 'z' * 64, 'a' * 63]:
            with self.assertRaises(ValueError):
                create_checkpoint(value, {}, 0, 0, None, [])
        for count, reviewed in [(True, 0), (1, False), (1.0, 0), (3, 0)]:
            with self.assertRaises(ValueError):
                create_checkpoint(document_fingerprint(self.pdf), {}, count, reviewed, None, [])


if __name__ == "__main__":
    unittest.main()
