"""Real SDK test of the main due-diligence financial submission guardrail.

No network calls: scripted SDK Model, already-approved RunState, and a restored
unreviewed submission that MUST NOT be overwritten by a new tool call.
"""
import json
import unittest

from agents import Agent, Runner, function_tool, set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tests.test_real_sdk_offline_pause_resume import ScriptedOfflineModel


class MainFinancialResumeGuardTests(unittest.TestCase):
    def test_approved_sdk_call_cannot_bypass_unreviewed_submission(self):
        import app
        set_tracing_disabled(True)
        pdf = b"synthetic full agent finance resume fixture"
        fields = {
            "company": "Synthetic Company", "fiscal_year": 2025,
            "currency": "USD", "units": "millions",
            "revenue_current": 120.0, "revenue_previous": 100.0,
            "gross_profit": 80.0, "net_income": 30.0,
            "reported_revenue_growth": 20.0, "reported_gross_margin": 66.67,
            "reported_net_margin": 25.0,
            "source_page": 1, "revenue_current_page": 1,
            "revenue_previous_page": 1, "gross_profit_page": 1,
            "net_income_page": 1,
        }
        previous = {
            "company": "Synthetic Company", "fiscal_year": 2025,
            "currency": "USD", "units": "millions",
            "revenue_current": 130.0, "revenue_previous": 100.0,
            "gross_profit": 80.0, "net_income": 30.0,
            "reported": {"revenue_growth": 30.0,
                         "gross_margin": 61.54, "net_margin": 23.08},
            "source_page": 1,
            "source_pages": {"revenue_current": 1, "revenue_previous": 1,
                             "gross_profit": 1, "net_income": 1},
        }
        model = ScriptedOfflineModel()
        model.responses = [
            [ResponseFunctionToolCall(
                id="f_main_finance", call_id="c_main_finance", type="function_call",
                name="submit_financial_data", arguments=json.dumps(fields),
                status="completed",
            )],
            [ResponseOutputMessage(
                id="m_main_finance", type="message", role="assistant",
                status="completed", content=[ResponseOutputText(
                    type="output_text",
                    text="Offline financial resumption with review pending.",
                    annotations=[],
                )],
            )],
        ]

        @function_tool(needs_approval=True)
        def submit_financial_data(
            company: str, fiscal_year: int, currency: str, units: str,
            revenue_current: float, revenue_previous: float,
            gross_profit: float, net_income: float,
            reported_revenue_growth: float, reported_gross_margin: float,
            reported_net_margin: float, source_page: int,
            revenue_current_page: int, revenue_previous_page: int,
            gross_profit_page: int, net_income_page: int,
        ) -> str:
            """Request a financial submission that must receive reviewer approval."""
            raise AssertionError("Initial paused tool must never execute")

        first = Runner.run_sync(
            Agent(name="Offline initial approval", model=model,
                  tools=[submit_financial_data]),
            "Pause a financial submission in the offline SDK.",
        )
        self.assertEqual(len(first.interruptions), 1)
        sdk_state = first.to_state()
        sdk_state.approve(sdk_state.get_interruptions()[0])
        checkpoint = create_checkpoint(
            document_fingerprint(pdf), previous, 1, 0, None,
            ["read_page", "submit_financial_data"],
        )
        report, _, financial, evaluation = app.run_due_diligence(
            ["Synthetic financial statement. FY2025 revenue 120; FY2024 revenue 100. "
             "Gross profit 80, net income 30."],
            restored_checkpoint=checkpoint,
            resume_pdf_bytes=pdf,
            sdk_resume_state=sdk_state,
            offline_scripted_model=model,
            financial_approval_required=True,
        )
        self.assertEqual(financial["revenue_current"], 130.0)
        self.assertEqual(financial["revenue_previous"], 100.0)
        self.assertEqual(model.calls, 2)
        self.assertIn("review", report.lower())


if __name__ == "__main__":
    unittest.main()
