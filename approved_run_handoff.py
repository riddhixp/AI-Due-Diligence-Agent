"""Offline handoff preparation after SDK approvals are applied.

Returns references only to the in-memory SDK RunState and validated financial
state. It does not call Runner.run or claim that tool closure rebinding works.
"""
from copy import deepcopy
from tool_state_rebinding import prepare_tool_state


def prepare_approved_run_handoff(queue, document_sha256, checkpoint, pdf_bytes):
    if not isinstance(queue, dict) or not queue.get("decisions_applied"):
        raise ValueError("SDK_DECISIONS_NOT_APPLIED")
    if queue.get("document_sha256") != document_sha256:
        raise ValueError("DOCUMENT_MISMATCH")
    state = queue.get("state")
    if state is None:
        raise ValueError("MISSING_SDK_RUN_STATE")
    restored = prepare_tool_state(checkpoint, pdf_bytes)
    return {
        "sdk_state": state,
        "financial_state": deepcopy(restored),
        "submission_count": restored["submission_attempts"]["count"],
        "reviewed_count": restored["review_state"]["reviewed_count"],
        "ready_for_live_run": False,
        "reason": "SDK_AGENT_TOOL_CLOSURES_NOT_REBOUND",
    }
