"""Record a one-time, PDF-bound SDK approval decision without model calls."""
from investigation_checkpoint import document_fingerprint
from tool_state_rebinding import prepare_tool_state


def decide_live_financial_pause(handoff, pdf_bytes, approved):
    if handoff.get("status") != "AWAITING_APPROVAL":
        raise ValueError("LIVE_APPROVAL_ALREADY_DECIDED")
    if type(approved) is not bool:
        raise ValueError("INVALID_APPROVAL_DECISION")
    if document_fingerprint(pdf_bytes) != handoff["checkpoint"]["document_sha256"]:
        raise ValueError("DOCUMENT_MISMATCH")
    restored = prepare_tool_state(handoff["checkpoint"], pdf_bytes)
    counts = restored["review_state"]
    if ("page_reads" in handoff or "reads_at_review" in handoff):
        if (handoff.get("page_reads") != counts["page_reads"]
                or handoff.get("reads_at_review") != counts["reads_at_review"]):
            raise ValueError("PAUSE_READ_COUNTER_MISMATCH")
    state = handoff["sdk_state"]
    get_requests = getattr(state, "get_interruptions", None)
    if not callable(get_requests):
        raise ValueError("SDK_INTERRUPTION_UNAVAILABLE")
    requests = get_requests()
    if not isinstance(requests, list) or len(requests) != 1:
        raise ValueError("SINGLE_FINANCIAL_APPROVAL_REQUIRED")
    method = getattr(state, "approve" if approved else "reject", None)
    if not callable(method):
        raise ValueError("SDK_DECISION_METHOD_UNAVAILABLE")
    handoff["status"] = "APPLYING_APPROVAL"
    if approved:
        method(requests[0], always_approve=False)
    else:
        method(
            requests[0], always_reject=False,
            rejection_message="Financial submission declined by reviewer.",
        )
    handoff["status"] = "APPROVED" if approved else "REJECTED"
    return {
        "status": handoff["status"],
        "model_resumed": False,
        "live_resume_enabled": False,
    }
