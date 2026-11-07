import unittest

from audit_appendix import append_audit_appendix


class AuditAppendixTests(unittest.TestCase):
    def test_status_is_reported_without_source_content(self):
        result = append_audit_appendix(
            "# Diligence",
            {"outcome": "CORRECTION_STILL_NEEDS_REVIEW",
             "submissions": 2, "latest_submission_reviewed": True},
            {"sequence_ok": True, "issues": []},
        )
        self.assertIn("CORRECTION_STILL_NEEDS_REVIEW", result)
        self.assertIn("Latest submission reviewed: Yes", result)
        self.assertIn("does not establish", result)

    def test_missing_audit_uses_conservative_values(self):
        result = append_audit_appendix("# Diligence", {}, {})
        self.assertIn("UNKNOWN", result)
        self.assertIn("Latest submission reviewed: No", result)

    def test_failed_sequence_issues_shown(self):
        result = append_audit_appendix(
            "Report", {"outcome": "LATEST_SUBMISSION_UNREVIEWED"},
            {"sequence_ok": False, "issues": ["NO_REVIEW_TOOL_CALL"]},
        )
        self.assertIn("NO_REVIEW_TOOL_CALL", result)

    def test_idempotent(self):
        a = append_audit_appendix("Report", {}, {})
        b = append_audit_appendix(a, {}, {})
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
