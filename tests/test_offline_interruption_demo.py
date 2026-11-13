import unittest
from offline_interruption_demo import simulate_turn_limit
from scripts.create_conflict_test_fixture import PAGE_ONE, PAGE_TWO


class OfflineInterruptionTests(unittest.TestCase):
    def test_preserves_unreviewed_figures_with_clear_warning(self):
        report, validation, financial, evaluation = simulate_turn_limit(
            ["\n".join(PAGE_ONE), "\n".join(PAGE_TWO)]
        )
        self.assertEqual(financial["revenue_current"], 130)
        self.assertIn("Latest submission reviewed: No", report)
        self.assertEqual(evaluation["evaluation"], "INTERRUPTED_TURN_LIMIT")
        self.assertIn("AGENT_MAX_TURNS_EXCEEDED", evaluation["issues"])
        self.assertFalse(evaluation["can_resume"])
        self.assertEqual(evaluation["api_calls"], 0)
        self.assertIsNone(validation)

    def test_checkpoint_round_trip_preserves_unreviewed_state(self):
        from investigation_checkpoint import create_checkpoint, document_fingerprint
        from financial_state_restore import restore_financial_state
        pdf = b"fixed fixture"
        checkpoint = create_checkpoint(
            document_fingerprint(pdf),
            {"revenue_current": 130, "revenue_previous": 100},
            1, 0, None, ["read_page", "submit_financial_data"]
        )
        restored = restore_financial_state(checkpoint, pdf)
        self.assertEqual(restored["reviewed_count"], 0)
        self.assertIsNone(restored["review_status"])
        self.assertEqual(restored["observed_tool_calls"][-1], "submit_financial_data")

    def test_reject_real_reports(self):
        with self.assertRaises(ValueError):
            simulate_turn_limit(["Real company annual report"])


if __name__ == "__main__":
    unittest.main()
