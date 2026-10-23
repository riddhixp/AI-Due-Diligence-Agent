"""Record a one-time, PDF-bound SDK approval decision without model calls."""
import threading
import weakref

from investigation_checkpoint import document_fingerprint
from tool_state_rebinding import prepare_tool_state
from financial_approval_preview import pending_financial_request


# Cleanup can run synchronously during SDK mutation on this same thread.
_decision_lock = threading.RLock()
_decided_states = {}


def _forget_decision(key, reference):
    with _decision_lock:
        if _decided_states.get(key) is reference:
            _decided_states.pop(key, None)


def decide_live_financial_pause(handoff, pdf_bytes, approved, *, expected_request_sha256=None):
    """Apply one decision per state identity, including through copied handoffs.

    Claims survive SDK failures, but hold only weak references to transcript state.
    Validation failures leave the request available for a corrected review.
    """
    with _decision_lock:
        return _decide_locked(handoff, pdf_bytes, approved,
                              expected_request_sha256=expected_request_sha256)


def _decide_locked(handoff, pdf_bytes, approved, *, expected_request_sha256=None):
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
    key = id(state)
    previous = _decided_states.get(key)
    if previous is not None and previous() is state:
        raise ValueError("SDK_APPROVAL_ALREADY_DECIDED")
    request, _, fingerprint = pending_financial_request(state)
    if expected_request_sha256 is not None and fingerprint != expected_request_sha256:
        raise ValueError("FINANCIAL_APPROVAL_REQUEST_CHANGED")
    method = getattr(state, "approve" if approved else "reject", None)
    if not callable(method):
        raise ValueError("SDK_DECISION_METHOD_UNAVAILABLE")
    try:
        reference = weakref.ref(state, lambda ref, key=key: _forget_decision(key, ref))
    except TypeError as error:
        raise ValueError("SDK_APPROVAL_STATE_NOT_WEAKREFABLE") from error
    _decided_states[key] = reference
    handoff["status"] = "APPLYING_APPROVAL"
    try:
        if approved:
            method(request, always_approve=False)
        else:
            method(
                request, always_reject=False,
                rejection_message="Financial submission declined by reviewer.",
            )
    except BaseException:
        handoff["status"] = "FAILED"
        raise
    handoff["decision_request_sha256"] = fingerprint
    handoff["status"] = "APPROVED" if approved else "REJECTED"
    return {
        "status": handoff["status"],
        "model_resumed": False,
        "live_resume_enabled": False,
    }
