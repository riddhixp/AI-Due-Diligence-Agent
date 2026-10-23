"""Classify SDK run termination without implying unsupported continuation.

The Agents SDK documents RunState continuation for supported pause boundaries.
A MaxTurnsExceeded exception alone is not a reusable RunState.
This module is deterministic and never calls a model.
"""


def classify_run_boundary(*, completed=False, paused_state=None, max_turns_error=False):
    if completed and (paused_state is not None or max_turns_error):
        raise ValueError("CONTRADICTORY_RUN_TERMINATION")
    if paused_state is not None and max_turns_error:
        raise ValueError("CONTRADICTORY_RUN_TERMINATION")
    if completed:
        return {
            "status": "COMPLETED",
            "can_resume": False,
            "reason": "RUN_ALREADY_FINISHED",
        }
    if max_turns_error:
        return {
            "status": "INTERRUPTED_TURN_LIMIT",
            "can_resume": False,
            "reason": "MAX_TURNS_IS_NOT_A_SAVED_RUN_STATE",
        }
    if paused_state is not None:
        return {
            "status": "SDK_PAUSED_STATE_PRESENT",
            "can_resume": False,
            "reason": "FINANCIAL_TOOL_REBINDING_NOT_VALIDATED",
        }
    return {
        "status": "NO_RUN_STATE",
        "can_resume": False,
        "reason": "NO_SUPPORTED_PAUSE_BOUNDARY",
    }
