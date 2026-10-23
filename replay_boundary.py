"""Offline-only checks for an interrupted conversation's replay boundary.

No model calls and no transcript persistence. A syntactically valid history
is still not evidence that the SDK can resume tool state safely.
"""


def validate_replay_boundary(items):
    """Identify tool calls with no corresponding tool response."""
    if not isinstance(items, list) or not items:
        return {"safe_boundary": False, "reason": "EMPTY_TRANSCRIPT"}

    pending = set()
    for item in items:
        if not isinstance(item, dict):
            return {"safe_boundary": False, "reason": "UNRECOGNISED_ITEM"}
        kind = item.get("type")
        if kind == "function_call":
            call_id = item.get("call_id")
            if not isinstance(call_id, str) or not call_id or call_id in pending:
                return {"safe_boundary": False, "reason": "INVALID_CALL_ID"}
            pending.add(call_id)
        elif kind == "function_call_output":
            call_id = item.get("call_id")
            if call_id not in pending:
                return {"safe_boundary": False, "reason": "ORPHAN_TOOL_OUTPUT"}
            pending.remove(call_id)
        elif kind in ("message", "reasoning"):
            continue
        else:
            return {"safe_boundary": False, "reason": "UNRECOGNISED_ITEM"}

    if pending:
        return {"safe_boundary": False, "reason": "PENDING_TOOL_CALL",
                "pending_count": len(pending)}
    return {"safe_boundary": True, "reason": "STRUCTURALLY_COMPLETE",
            "can_resume": False}
