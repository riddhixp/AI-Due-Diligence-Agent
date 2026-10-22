"""Typed, memory-only handoff for a genuine SDK financial approval pause.

No file writes, no SDK resume, and no model calls in this module.
"""
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state


class SDKFinancialApprovalPaused(RuntimeError):
    """Expose the paused SDK state to a trusted caller without printing it."""

    def __init__(self, handoff):
        super().__init__("SDK_APPROVAL_PAUSED: financial approval required; live resume disabled.")
        self.handoff = handoff


def make_financial_pause_handoff(
    capture, pdf_bytes, financial_data, submission_count, reviewed_count,
    review_status, tool_calls, page_reads, reads_at_review,
):
    if not capture.get("paused") or capture.get("state") is None:
        raise ValueError("NO_CAPTURED_SDK_APPROVAL")
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ValueError("ORIGINAL_PDF_REQUIRED")
    if page_reads < 0 or reads_at_review < 0 or reads_at_review > page_reads:
        raise ValueError("INVALID_PAGE_READ_COUNTERS")
    checkpoint = create_checkpoint(
        document_fingerprint(pdf_bytes), financial_data, submission_count,
        reviewed_count, review_status, tool_calls,
    )
    restored = prepare_tool_state(checkpoint, pdf_bytes)
    counters = restored["review_state"]
    if (counters["page_reads"] != page_reads
            or counters["reads_at_review"] != reads_at_review):
        raise ValueError("PAUSE_READ_COUNTER_MISMATCH")
    return {
        "sdk_state": capture["state"],
        "checkpoint": checkpoint,
        "page_reads": page_reads,
        "reads_at_review": reads_at_review,
        "status": "AWAITING_APPROVAL",
        "live_resume_enabled": False,
    }


def public_financial_pause_status(handoff):
    checkpoint = handoff["checkpoint"]
    return {
        "status": handoff["status"],
        "submitted_count": checkpoint["submission_count"],
        "reviewed_count": checkpoint["reviewed_count"],
        "review_status": checkpoint["review_status"],
        "page_reads": handoff["page_reads"],
        "live_resume_enabled": False,
    }
