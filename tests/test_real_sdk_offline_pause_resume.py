"""Real Agents SDK pause/resume integration, using a zero-network scripted model.

This exercises Runner.run_sync and RunState, not an application fake Runner.
"""
import unittest
from openai.types.responses import (
    ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText,
)
from agents import Agent, Runner, function_tool, set_tracing_disabled
from agents.models.interface import Model
from agents.items import ModelResponse
from agents.usage import Usage


class ScriptedOfflineModel(Model):
    def __init__(self):
        self.responses = [
            [ResponseFunctionToolCall(
                id="fc_test_1", call_id="call_test_1", type="function_call",
                name="submit_approved_financials", arguments='{"revenue":120}',
                status="completed",
            )],
            [ResponseOutputMessage(
                id="msg_test_1", type="message", role="assistant",
                status="completed", content=[
                    ResponseOutputText(
                        type="output_text", text="Financial workflow completed.",
                        annotations=[],
                    ),
                ],
            )],
        ]
        self.calls = 0

    async def get_response(self, *args, **kwargs):
        self.calls += 1
        if not self.responses:
            raise AssertionError("Unexpected further model request")
        return ModelResponse(
            output=self.responses.pop(0), usage=Usage(),
            response_id="offline-scripted-response",
        )

    async def stream_response(self, *args, **kwargs):
        raise AssertionError("No network or streaming permitted")
        yield


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
