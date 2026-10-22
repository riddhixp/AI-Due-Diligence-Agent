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

    executed = []

    @function_tool(needs_approval=True)
    def submit_approved_financials(revenue: float) -> str:
        """Submit synthetic financial revenue for approval testing."""
        executed.append(revenue)
        return "Synthetic financial submission accepted"

    agent = Agent(
        name="Offline SDK approval interface demo", model=model,
        tools=[submit_approved_financials],
    )
    result = Runner.run_sync(agent, "Offline approval fixture")
    queue = prepare_approval_queue(result, document_fingerprint(pdf_bytes))
    if not queue["ready"] or len(queue["pending"]) != 1:
        raise ValueError("SDK_OFFLINE_APPROVAL_PAUSE_FAILED")
    queue["offline_sdk_demo"] = True
    queue["_offline_agent"] = agent
    queue["_offline_executed"] = executed
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


def resume_sdk_offline_approval(queue, pdf_bytes):
    """Resume the actual SDK with its scripted offline model only."""
    if not queue.get("offline_sdk_demo") or not queue.get("decisions_applied"):
        raise ValueError("SDK_APPROVAL_NOT_APPLIED")
    if queue.get("document_sha256") != document_fingerprint(pdf_bytes):
        raise ValueError("DOCUMENT_MISMATCH")
    if queue.get("offline_resumed"):
        raise ValueError("SDK_DEMO_ALREADY_RESUMED")
    agent = queue.get("_offline_agent")
    if agent is None or not isinstance(agent.model, ScriptedOfflineModel):
        raise ValueError("OFFLINE_MODEL_REQUIRED")
    queue["offline_resumed"] = True
    completed = Runner.run_sync(agent, queue["state"])
    return {
        "finished": bool(completed.final_output),
        "executed_submissions": list(queue["_offline_executed"]),
        "model_resumed": True,
        "external_api_calls": 0,
        "scripted_model": True,
    }
