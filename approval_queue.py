"""Safe, in-memory approval queue for a paused SDK RunState.

An approval decision here is *not* an SDK resume. No model calls occur.
"""
from sdk_pause_capture import capture_approval_pause, pause_public_status


def prepare_approval_queue(result, document_sha256):
    if not isinstance(document_sha256, str) or len(document_sha256) != 64:
        raise ValueError("INVALID_DOCUMENT_FINGERPRINT")
    captured = capture_approval_pause(result)
    if not captured["paused"]:
        return {"ready": False, "reason": captured["reason"], "pending": []}
    return {
        "ready": True, "reason": "AWAITING_USER_DECISION",
        "document_sha256": document_sha256,
        "state": captured["state"],
        "pending": [
            {"index": index, "decision": "PENDING"}
            for index in range(captured["approval_count"])
        ],
        "can_resume": False,
    }


def decide_approval(queue, document_sha256, index, approved):
    if not queue.get("ready"):
        raise ValueError("NO_PENDING_APPROVAL_QUEUE")
    if queue.get("document_sha256") != document_sha256:
        raise ValueError("DOCUMENT_MISMATCH")
    if type(index) is not int or not 0 <= index < len(queue["pending"]):
        raise ValueError("INVALID_APPROVAL_INDEX")
    if type(approved) is not bool:
        raise ValueError("INVALID_APPROVAL_DECISION")
    item = queue["pending"][index]
    if item["decision"] != "PENDING":
        raise ValueError("APPROVAL_ALREADY_DECIDED")
    item["decision"] = "APPROVED" if approved else "REJECTED"
    return queue


def approval_public_status(queue):
    """Never expose RunState or raw tool arguments in dashboard data."""
    pending = queue.get("pending", [])
    return {
        "ready": bool(queue.get("ready", False)),
        "reason": queue.get("reason", "UNKNOWN"),
        "approvals": [item["decision"] for item in pending],
        "can_resume": False,
    }
