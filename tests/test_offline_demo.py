import unittest

from offline_demo import simulate_conflict_correction
from scripts.create_conflict_test_fixture import PAGE_ONE, PAGE_TWO


class OfflineDemoTests(unittest.TestCase):
    def test_scripted_correction_works_without_api(self):
        report, validation, data, evaluation = simulate_conflict_correction(
            ["\n".join(PAGE_ONE), "\n".join(PAGE_TWO)]
        )
        self.assertEqual(data["revenue_current"], 120)
        self.assertTrue(validation)
        self.assertTrue(all(item["status"] == "PASS" for item in validation.values()))
        self.assertEqual(evaluation["initial_review_status"], "NEEDS_REVIEW")
        self.assertEqual(evaluation["evaluation"], "PRELIMINARY_PASS")
        self.assertTrue(evaluation["simulation"])
        self.assertEqual(evaluation["api_calls"], 0)
        self.assertIn("scripted", report.lower())

    def test_cannot_simulate_authentic_filing(self):
        with self.assertRaises(ValueError):
            simulate_conflict_correction(["Real company annual report"])

    def test_cannot_simulate_unsupported_fixture(self):
        with self.assertRaises(ValueError):
            simulate_conflict_correction([PAGE_ONE[0], "unrelated page"])


if __name__ == "__main__":
    unittest.main()
