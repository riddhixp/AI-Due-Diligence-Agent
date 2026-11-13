"""Capture a supported SDK pause boundary conservatively and in memory.

Only a RunResult with pending approval interruptions can yield a RunState
here. The captured state can contain document or tool data and must not
be logged or persisted by default. No API calls are made.
"""


def capture_approval_pause(result):
    pending = getattr(result, "interruptions", None)
    if not isinstance(pending, (list, tuple)) or not pending:
        return {"paused": False, "reason": "NO_PENDING_APPROVALS", "state": None}

    to_state = getattr(result, "to_state", None)
    if not callable(to_state):
        return {"paused": False, "reason": "SDK_STATE_EXPORT_UNAVAILABLE", "state": None}

    try:
        state = to_state()
    except Exception:
        return {"paused": False, "reason": "SDK_STATE_EXPORT_FAILED", "state": None}

    if state is None or not callable(getattr(state, "get_interruptions", None)):
        return {"paused": False, "reason": "INVALID_SDK_RUN_STATE", "state": None}

    try:
        restored_approvals = state.get_interruptions()
    except Exception:
        return {"paused": False, "reason": "SDK_INTERRUPTION_INSPECTION_FAILED", "state": None}

    if not restored_approvals:
        return {"paused": False, "reason": "PAUSE_APPROVALS_NOT_PRESERVED", "state": None}

    return {
        "paused": True,
        "reason": "SDK_APPROVAL_PAUSE_CAPTURED",
        "approval_count": len(restored_approvals),
        "state": state,
        "can_resume": False,  # Financial closure state is not yet reconnected.
    }


def pause_public_status(capture):
    """Strip non-serializable, potentially sensitive SDK state for UI output."""
    return {
        "paused": bool(capture.get("paused", False)),
        "reason": capture.get("reason", "UNKNOWN"),
        "approval_count": capture.get("approval_count", 0),
        "can_resume": False,
    }
