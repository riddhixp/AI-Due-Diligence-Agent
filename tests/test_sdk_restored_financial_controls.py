"""Actual SDK approval/resume with restored financial guardrails, no network."""
import unittest
from agents import Agent, Runner, function_tool, set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from tests.test_real_sdk_offline_pause_resume import ScriptedOfflineModel
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state
from investigation_control import submission_block_reason


class RestoredSDKIntegrationTests(unittest.TestCase):
    def setUp(self):
        set_tracing_disabled(True)
        self.pdf = b"synthetic fixture"
        self.checkpoint = create_checkpoint(
            document_fingerprint(self.pdf),
            {"revenue_current": 130},
            1, 0, None,
            ["read_page", "submit_financial_data"],
        )
        self.restored = prepare_tool_state(self.checkpoint, self.pdf)
        self.executed = []
        self.model = ScriptedOfflineModel()
        self.model.responses[0][0].name = "submit_financial_data"
        self.model.responses[0][0].arguments = '{"revenue":120}'

        @function_tool(needs_approval=True)
        def submit_financial_data(revenue: float) -> str:
            """Submit corrected revenue only after existing controls permit it."""
            review = self.restored["review_state"]
            count = self.restored["submission_attempts"]["count"]
            refusal = submission_block_reason(
                count, review["reviewed_count"], review["status"],
                review["page_reads"] - review["reads_at_review"],
            )
            if refusal:
                return refusal
            self.executed.append(revenue)
            self.restored["submission_attempts"]["count"] += 1
            return "Accepted"

        self.agent = Agent(name="Restored offline SDK test",
                           model=self.model, tools=[submit_financial_data])

    def test_approval_does_not_bypass_pending_review(self):
        paused = Runner.run_sync(self.agent, "Offline continuation fixture")
        self.assertEqual(len(paused.interruptions), 1)
        self.assertEqual(self.executed, [])
        state = paused.to_state()
        state.approve(state.get_interruptions()[0])
        completed = Runner.run_sync(self.agent, state)
        self.assertEqual(self.executed, [])
        self.assertEqual(self.restored["submission_attempts"]["count"], 1)
        self.assertEqual(completed.final_output, "Financial workflow completed.")

    def test_denial_does_not_execute_submission(self):
        paused = Runner.run_sync(self.agent, "Offline continuation fixture")
        state = paused.to_state()
        state.reject(state.get_interruptions()[0],
                     rejection_message="Financial review required")
        Runner.run_sync(self.agent, state)
        self.assertEqual(self.executed, [])
        self.assertEqual(self.restored["submission_attempts"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
