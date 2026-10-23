"""Real SDK pause/resume integration with a zero-network scripted model."""
import unittest
from agents import Agent, Runner, function_tool, set_tracing_disabled
from scripted_offline_model import ScriptedOfflineModel


class SDKOfflinePauseResumeTests(unittest.TestCase):
    def setUp(self):
        set_tracing_disabled(True)
        self.submissions = []
        self.model = ScriptedOfflineModel()

        @function_tool(needs_approval=True)
        def submit_approved_financials(revenue: float) -> str:
            """Record a test revenue figure after explicit approval."""
            self.submissions.append(revenue)
            return "Accepted"

        self.agent = Agent(
            name="Offline financial reviewer", model=self.model,
            tools=[submit_approved_financials],
            instructions="Only follow scripted test responses.",
        )

    def test_approval_pauses_before_submission_then_resumes(self):
        first = Runner.run_sync(self.agent, "Run offline financial test")
        self.assertEqual(len(first.interruptions), 1)
        self.assertEqual(self.submissions, [])
        self.assertEqual(self.model.calls, 1)
        state = first.to_state()
        pending = state.get_interruptions()
        self.assertEqual(len(pending), 1)
        state.approve(pending[0])
        final = Runner.run_sync(self.agent, state)
        self.assertEqual(self.submissions, [120])
        self.assertEqual(self.model.calls, 2)
        self.assertEqual(final.final_output, "Financial workflow completed.")

    def test_rejection_does_not_execute_financial_submission(self):
        first = Runner.run_sync(self.agent, "Run offline financial test")
        state = first.to_state()
        state.reject(
            state.get_interruptions()[0],
            rejection_message="Submission rejected by reviewer.",
        )
        final = Runner.run_sync(self.agent, state)
        self.assertEqual(self.submissions, [])
        self.assertEqual(self.model.calls, 2)
        self.assertEqual(final.final_output, "Financial workflow completed.")


if __name__ == "__main__":
    unittest.main()
