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

    def test_reject_real_reports(self):
        with self.assertRaises(ValueError):
            simulate_turn_limit(["Real company annual report"])


if __name__ == "__main__":
    unittest.main()
