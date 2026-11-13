import unittest
from types import SimpleNamespace
from offline_sdk_resume import dry_run_resume


class FakeRunner:
    offline_test_double = True

    def __init__(self):
        self.calls = []

    def run(self, agent, state):
        self.calls.append((agent, state))
        return "fake result"


class OfflineSDKResumeTests(unittest.TestCase):
    def setUp(self):
        self.state = object()
        self.agent = object()
        self.runner = FakeRunner()
        self.handoff = {
            "sdk_state": self.state,
            "financial_state": {
                "submission_attempts": {"count": 1},
                "review_state": {"reviewed_count": 0},
            },
            "ready_for_live_run": False,
            "reason": "SDK_AGENT_TOOL_CLOSURES_NOT_REBOUND",
        }

    def test_mock_resume_receives_same_state(self):
        result = dry_run_resume(self.handoff, self.agent, self.runner)
        self.assertEqual(self.runner.calls, [(self.agent, self.state)])
        self.assertEqual(result["submissions_preserved"], 1)
        self.assertFalse(result["model_resumed"])

    def test_real_runner_rejected(self):
        class UnmarkedRunner:
            def run(self, agent, state):
                raise AssertionError("Must not execute")
        with self.assertRaisesRegex(ValueError, "OFFLINE_RUNNER_REQUIRED"):
            dry_run_resume(self.handoff, self.agent, UnmarkedRunner())

    def test_live_flag_rejected(self):
        with self.assertRaisesRegex(ValueError, "LIVE_RESUME_NOT_VERIFIED"):
            dry_run_resume(self.handoff, self.agent, self.runner, allow_live=True)
        self.assertEqual(self.runner.calls, [])

    def test_invalid_handoff_rejected(self):
        self.handoff["sdk_state"] = None
        with self.assertRaisesRegex(ValueError, "MISSING_RESUME_STATE"):
            dry_run_resume(self.handoff, self.agent, self.runner)


if __name__ == "__main__":
    unittest.main()
