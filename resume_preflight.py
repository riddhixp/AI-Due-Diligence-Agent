"""Preflight a future resume attempt without making model calls.

Restoring Python counters does not by itself restore a model conversation.
Never advertise resumability unless all independent preconditions pass.
"""
from financial_state_restore import restore_financial_state
from replay_boundary import validate_replay_boundary


def resume_preflight(checkpoint, pdf_bytes, transcript):
    try:
        state = restore_financial_state(checkpoint, pdf_bytes)
    except (ValueError, TypeError, KeyError) as exc:
        return {"ready": False, "reason": str(exc)}

    structure = validate_replay_boundary(transcript)
    if not structure["safe_boundary"]:
        return {"ready": False, "reason": structure["reason"]}

    if checkpoint.get("model_conversation_saved") is not True:
        return {"ready": False, "reason": "MODEL_CONVERSATION_NOT_SAVED"}

    if state["submission_count"] and not any(
        name == "submit_financial_data" for name in state["observed_tool_calls"]
    ):
        return {"ready": False, "reason": "SUBMISSION_TRACE_MISSING"}

    return {
        "ready": False,
        "reason": "TOOL_STATE_REBINDING_NOT_IMPLEMENTED",
        "restored_submissions": state["submission_count"],
        "restored_reviews": state["reviewed_count"],
    }
