"""Validate an approval queue before any future SDK decision handoff.

This prepares a decision manifest only. It does not mutate RunState or call AI.
"""


def prepare_approval_handoff(queue, document_sha256):
    if not isinstance(queue, dict) or not queue.get("ready"):
        return {"handoff_ready": False, "reason": "NO_PENDING_APPROVAL_QUEUE"}
    if queue.get("document_sha256") != document_sha256:
        return {"handoff_ready": False, "reason": "DOCUMENT_MISMATCH"}
    if queue.get("state") is None:
        return {"handoff_ready": False, "reason": "MISSING_SDK_STATE"}
    pending = queue.get("pending")
    if not isinstance(pending, list) or not pending:
        return {"handoff_ready": False, "reason": "NO_APPROVAL_REQUESTS"}
    if any(item.get("decision") == "PENDING" for item in pending):
        return {"handoff_ready": False, "reason": "UNDECIDED_APPROVALS"}
    if any(item.get("decision") not in ("APPROVED", "REJECTED") for item in pending):
        return {"handoff_ready": False, "reason": "INVALID_APPROVAL_DECISION"}
    return {
        "handoff_ready": True,
        "reason": "OFFLINE_HANDOFF_PREPARED",
        "decisions": [item["decision"] for item in pending],
        "can_resume": False,
    }
