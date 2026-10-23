import unittest

from sdk_resume_policy import classify_run_boundary


class SDKResumePolicyTests(unittest.TestCase):
    def test_max_turns_does_not_claim_resume(self):
        result = classify_run_boundary(max_turns_error=True)
        self.assertFalse(result["can_resume"])
        self.assertEqual(result["reason"], "MAX_TURNS_IS_NOT_A_SAVED_RUN_STATE")

    def test_paused_sdk_state_is_not_enough(self):
        result = classify_run_boundary(paused_state=object())
        self.assertFalse(result["can_resume"])
        self.assertEqual(result["status"], "SDK_PAUSED_STATE_PRESENT")

    def test_completed_is_not_interrupted(self):
        result = classify_run_boundary(completed=True)
        self.assertEqual(result["status"], "COMPLETED")

    def test_missing_state_is_not_resumable(self):
        self.assertEqual(classify_run_boundary()["status"], "NO_RUN_STATE")

    def test_conflicting_states_rejected(self):
        with self.assertRaisesRegex(ValueError, "CONTRADICTORY"):
            classify_run_boundary(completed=True, max_turns_error=True)


if __name__ == "__main__":
    unittest.main()
