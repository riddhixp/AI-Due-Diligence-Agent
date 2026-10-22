"""Apply explicit decisions to an SDK RunState, without resuming the model.

This is a one-shot, in-memory bridge. The caller must separately restore
financial tool closures and explicitly initiate a paid Runner.run call.
"""
from approval_handoff import prepare_approval_handoff


def apply_approval_decisions(queue, document_sha256):
    manifest = prepare_approval_handoff(queue, document_sha256)
    if not manifest["handoff_ready"]:
        raise ValueError(manifest["reason"])
    if queue.get("decisions_applied"):
        raise ValueError("DECISIONS_ALREADY_APPLIED")

    state = queue["state"]
    get_interruptions = getattr(state, "get_interruptions", None)
    approve = getattr(state, "approve", None)
    reject = getattr(state, "reject", None)
    if not all(callable(x) for x in (get_interruptions, approve, reject)):
        raise ValueError("INVALID_SDK_APPROVAL_METHODS")

    requests = get_interruptions()
    if not isinstance(requests, list) or len(requests) != len(manifest["decisions"]):
        raise ValueError("APPROVAL_REQUEST_COUNT_MISMATCH")

    # Mark the queue as consumed before mutating the SDK state: a partial
    # failure must not make automatic retry apply decisions twice.
    queue["decisions_applied"] = True
    for approval_item, decision in zip(requests, manifest["decisions"]):
        if decision == "APPROVED":
            approve(approval_item, always_approve=False)
        else:
            reject(
                approval_item,
                always_reject=False,
                rejection_message="Financial submission declined by the reviewer.",
            )

    return {
        "decisions_applied": True,
        "count": len(requests),
        "model_resumed": False,
        "can_resume": False,
    }
