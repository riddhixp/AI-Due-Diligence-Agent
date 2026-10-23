"""Deterministic Agents SDK model for zero-network application demonstrations.

No credentials or model-provider client are used. Exhausted scripts fail closed.
"""
from openai.types.responses import (
    ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText,
)
from agents.models.interface import Model
from agents.items import ModelResponse
from agents.usage import Usage


class ScriptedOfflineModel(Model):
    is_offline_scripted_model = True
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

