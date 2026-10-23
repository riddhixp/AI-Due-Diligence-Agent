"""Exercise the actual app.run_due_diligence SDK resume path using no network."""
import unittest
from agents import Agent, Runner, function_tool, set_tracing_disabled
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from scripted_offline_model import ScriptedOfflineModel
from investigation_checkpoint import create_checkpoint, document_fingerprint


class FullAgentRunStateTests(unittest.TestCase):
    def test_main_agent_uses_saved_sdk_state_without_network(self):
        import app
        set_tracing_disabled(True)
        pdf = b"offline SDK test document"
        pages = ["Synthetic report with revenue 120 and previous revenue 100."]
        model = ScriptedOfflineModel()
        model.responses = [
            [ResponseFunctionToolCall(
                id="f_main", call_id="c_main", type="function_call",
                name="calculate_growth",
                arguments='{"current":120,"previous":100}',
                status="completed",
            )],
            [ResponseOutputMessage(
                id="m_main", type="message", role="assistant", status="completed",
                content=[ResponseOutputText(
                    type="output_text",
                    text="Offline scripted full agent continuation test.",
                    annotations=[],
                )],
            )],
        ]

        @function_tool(needs_approval=True)
        def calculate_growth(current: float, previous: float) -> str:
            """Require approval before calculating a synthetic growth rate."""
            return str((current / previous - 1) * 100)

        initial_agent = Agent(
            name="Full-agent SDK boundary fixture", model=model,
            tools=[calculate_growth],
        )
        pause = Runner.run_sync(initial_agent, "Offline test")
        self.assertEqual(len(pause.interruptions), 1)
        sdk_state = pause.to_state()
        sdk_state.approve(sdk_state.get_interruptions()[0])
        checkpoint = create_checkpoint(
            document_fingerprint(pdf), {}, 0, 0, None, [],
        )
        self.assertEqual(model.calls, 1)
        report, validation, financial, evaluation = app.run_due_diligence(
            pages, restored_checkpoint=checkpoint, resume_pdf_bytes=pdf,
            sdk_resume_state=sdk_state, offline_scripted_model=model,
        )
        self.assertIn("Investigation incomplete", report)
        self.assertFalse(evaluation["final_eligible"])
        self.assertIsNone(validation)
        self.assertEqual(model.calls, 2)
        self.assertEqual(financial, {})
        self.assertIsNone(validation)

    def test_default_paid_resume_is_rejected(self):
        import app
        pdf = b"offline"
        checkpoint = create_checkpoint(
            document_fingerprint(pdf), {}, 0, 0, None, [],
        )
        with self.assertRaisesRegex(ValueError, "LIVE_RESUME_DISABLED"):
            app.run_due_diligence(
                ["Synthetic page"], restored_checkpoint=checkpoint,
                resume_pdf_bytes=pdf, sdk_resume_state=object(),
            )


if __name__ == "__main__":
    unittest.main()
