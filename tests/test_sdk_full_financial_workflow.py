"""Real SDK offline integration: restored submission -> review -> correction.

This exercises approval, SDK RunState continuation, and the actual financial
review and submission guardrails with a scripted zero-network Model.
"""
import unittest

from agents import Agent, Runner, function_tool, set_tracing_disabled
from openai.types.responses import (
    ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText,
)
from scripted_offline_model import ScriptedOfflineModel
from tests.test_investigation_scenarios import PAGES, supported_submission
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state
from investigation_control import submission_block_reason
from agent_financial_review import review_financial_evidence


class FullWorkflowOfflineSDKTests(unittest.TestCase):
    def test_review_then_recheck_then_correction_preserves_counters(self):
        set_tracing_disabled(True)
        original = supported_submission()
        original["revenue_current"] = 130
        original["reported"]["revenue_growth"] = 30
        pdf = b"complete offline workflow synthetic fixture"
        checkpoint = create_checkpoint(
            document_fingerprint(pdf), original, 1, 0, None,
            ["read_page", "submit_financial_data"],
        )
        state = prepare_tool_state(checkpoint, pdf)
        trace = state["observed_tool_calls"]
        review = state["review_state"]
        counts = state["submission_attempts"]
        corrected = supported_submission()
        model = ScriptedOfflineModel()
        model.responses = [
            [ResponseFunctionToolCall(
                id="fc1", call_id="c1", type="function_call",
                name="review_submitted_financials", arguments="{}", status="completed",
            )],
            [ResponseFunctionToolCall(
                id="fc2", call_id="c2", type="function_call",
                name="read_page", arguments='{"page_number":1}', status="completed",
            )],
            [ResponseFunctionToolCall(
                id="fc3", call_id="c3", type="function_call",
                name="submit_financial_data", arguments='{"revenue":120}', status="completed",
            )],
            [ResponseFunctionToolCall(
                id="fc4", call_id="c4", type="function_call",
                name="review_submitted_financials", arguments="{}", status="completed",
            )],
            [ResponseOutputMessage(
                id="m1", type="message", role="assistant", status="completed",
                content=[ResponseOutputText(
                    type="output_text", text="Synthetic review complete.",
                    annotations=[],
                )],
            )],
        ]

        @function_tool
        def review_submitted_financials() -> str:
            """Review the currently accepted financial figures."""
            result = review_financial_evidence(PAGES, state["financial_submission"])
            trace.append("review_submitted_financials")
            review["reviewed_count"] = counts["count"]
            review["status"] = result["status"]
            review["reads_at_review"] = review["page_reads"]
            return result["status"]

        @function_tool
        def read_page(page_number: int) -> str:
            """Read the cited synthetic PDF page."""
            trace.append("read_page")
            review["page_reads"] += 1
            return PAGES[page_number - 1]

        @function_tool(needs_approval=True)
        def submit_financial_data(revenue: float) -> str:
            """Submit corrected numbers if the prior review allows it."""
            refusal = submission_block_reason(
                counts["count"], review["reviewed_count"], review["status"],
                review["page_reads"] - review["reads_at_review"],
            )
            if refusal:
                return refusal
            if revenue != corrected["revenue_current"]:
                return "INVALID_TEST_REVENUE"
            state["financial_submission"] = corrected.copy()
            counts["count"] += 1
            review["status"] = None
            trace.append("submit_financial_data")
            return "ACCEPTED"

        agent = Agent(
            name="Financial-review offline SDK integration",
            model=model,
            tools=[review_submitted_financials, read_page, submit_financial_data],
        )
        first = Runner.run_sync(agent, "Scripted offline financial workflow")
        self.assertEqual(len(first.interruptions), 1)
        self.assertEqual(counts["count"], 1)
        self.assertEqual(review["reviewed_count"], 1)
        self.assertEqual(review["status"], "NEEDS_REVIEW")
        self.assertEqual(review["page_reads"] - review["reads_at_review"], 1)

        sdk_state = first.to_state()
        sdk_state.approve(sdk_state.get_interruptions()[0])
        finished = Runner.run_sync(agent, sdk_state)
        self.assertEqual(finished.final_output, "Synthetic review complete.")
        self.assertEqual(counts["count"], 2)
        self.assertEqual(review["reviewed_count"], 2)
        self.assertEqual(review["status"], "PRELIMINARY_CHECKS_PASSED")
        self.assertEqual(trace.count("submit_financial_data"), 2)
        self.assertEqual(model.calls, 5)


if __name__ == "__main__":
    unittest.main()
