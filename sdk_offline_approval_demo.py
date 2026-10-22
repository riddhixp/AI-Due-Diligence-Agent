"""Real Agents SDK approval pause generated without API calls.

A scripted Model supplies the tool request; the real SDK creates RunState.
The Streamlit demo records decisions but does not resume a model.
"""
from agents import Agent, Runner, function_tool
from investigation_checkpoint import document_fingerprint
from approval_queue import prepare_approval_queue, decide_approval, approval_public_status
from sdk_approval_decisions import apply_approval_decisions
from tests.test_real_sdk_offline_pause_resume import ScriptedOfflineModel


def start_sdk_offline_approval(pdf_bytes):
    model = ScriptedOfflineModel()

    @function_tool(needs_approval=True)
    def submit_approved_financials(revenue: float) -> str:
        """Submit synthetic financial revenue for approval testing."""
        raise AssertionError("Offline approval demo must not execute financial tools")

    agent = Agent(
        name="Offline SDK approval interface demo", model=model,
        tools=[submit_approved_financials],
    )
    result = Runner.run_sync(agent, "Offline approval fixture")
    queue = prepare_approval_queue(result, document_fingerprint(pdf_bytes))
    if not queue["ready"] or len(queue["pending"]) != 1:
        raise ValueError("SDK_OFFLINE_APPROVAL_PAUSE_FAILED")
    queue["offline_sdk_demo"] = True
    return queue


def decide_sdk_offline_approval(queue, pdf_bytes, approved):
    if not queue.get("offline_sdk_demo"):
        raise ValueError("NOT_AN_OFFLINE_SDK_DEMO")
    digest = document_fingerprint(pdf_bytes)
    decide_approval(queue, digest, 0, approved)
    applied = apply_approval_decisions(queue, digest)
    return {
        **approval_public_status(queue),
        "sdk_decision_applied": applied["decisions_applied"],
        "model_resumed": False,
        "api_calls": 0,
    }
