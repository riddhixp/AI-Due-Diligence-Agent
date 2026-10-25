"""Prepare a document-bound, explicit resume preflight with no Runner call."""
import re
from io import BytesIO
from pypdf import PdfReader
from financial_approval_preview import pending_financial_request
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
    receipt = handoff.get("decision_request_sha256")
    if not isinstance(receipt, str) or re.fullmatch(r"[0-9a-f]{64}", receipt) is None:
        raise ValueError("MISSING_FINANCIAL_DECISION_RECEIPT")
    try:
        _, values, fingerprint = pending_financial_request(sdk_state)
    except ValueError as error:
        raise ValueError("FINANCIAL_APPROVAL_REQUEST_CHANGED") from error
    if fingerprint != receipt:
        raise ValueError("FINANCIAL_APPROVAL_REQUEST_CHANGED")
    try:
        pages = [page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages]
    except Exception as error:
        raise ValueError("READABLE_PDF_REQUIRED") from error
    if not pages or not any(page.strip() for page in pages):
        raise ValueError("READABLE_PDF_REQUIRED")
    if any(event["page"] > len(pages) for event in restored["page_read_events"]):
        raise ValueError("INVALID_PAGE_READ_HISTORY")
    if any(value is not None and value > len(pages)
           for field, value in values.items()
           if field == "source_page" or field.endswith("_page")):
        raise ValueError("FINANCIAL_APPROVAL_PAGE_OUT_OF_RANGE")
    return {
        "status": "APPROVED_PREFLIGHT_ONLY",
        "submission_count": restored["submission_attempts"]["count"],
        "reviewed_count": restored["review_state"]["reviewed_count"],
        "financial_review_status": restored["review_state"]["status"],
        "sdk_state_present": True,
        "approved_request_unchanged": True,
        "document_page_count": len(pages),
        "document_readable": True,
        "approved_citations_in_range": True,
        "model_conversation_restored": False,
        "model_resumed": False,
        "api_calls": 0,
        "ready_for_paid_resume": False,
        "reason": "PAID_CONTINUATION_DISABLED",
    }
