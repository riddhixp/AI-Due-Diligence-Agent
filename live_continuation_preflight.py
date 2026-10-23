"""Prepare a document-bound, explicit resume preflight with no Runner call."""
from investigation_checkpoint import document_fingerprint
from tool_state_rebinding import prepare_tool_state


def preflight_live_continuation(handoff, pdf_bytes):
    if not isinstance(handoff, dict):
        raise ValueError("INVALID_PAUSE_HANDOFF")
    if handoff.get("status") != "APPROVED":
        raise ValueError("APPROVAL_REQUIRED_FOR_CONTINUATION")
    if handoff.get("live_resume_enabled") is not False:
        raise ValueError("UNSAFE_RESUME_FLAG")
    checkpoint = handoff.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("MISSING_FINANCIAL_CHECKPOINT")
    if checkpoint.get("document_sha256") != document_fingerprint(pdf_bytes):
        raise ValueError("DOCUMENT_MISMATCH")
    sdk_state = handoff.get("sdk_state")
    if sdk_state is None or not callable(getattr(sdk_state, "get_interruptions", None)):
        raise ValueError("INVALID_SDK_RUN_STATE")
    restored = prepare_tool_state(checkpoint, pdf_bytes)
    if "page_reads" in handoff or "reads_at_review" in handoff:
        review = restored["review_state"]
        if (handoff.get("page_reads") != review["page_reads"]
                or handoff.get("reads_at_review") != review["reads_at_review"]):
            raise ValueError("PAUSE_READ_COUNTER_MISMATCH")
    return {
        "status": "APPROVED_PREFLIGHT_ONLY",
        "submission_count": restored["submission_attempts"]["count"],
        "reviewed_count": restored["review_state"]["reviewed_count"],
        "financial_review_status": restored["review_state"]["status"],
        "sdk_state_present": True,
        "model_conversation_restored": False,
        "model_resumed": False,
        "api_calls": 0,
        "ready_for_paid_resume": False,
        "reason": "PAID_CONTINUATION_DISABLED",
    }
