"""Construct safe mutable Python tool state from a validated checkpoint.

This prepares closure state, not a live SDK conversation resume.
"""
from copy import deepcopy
from financial_state_restore import restore_financial_state


def prepare_tool_state(checkpoint, pdf_bytes):
    state = restore_financial_state(checkpoint, pdf_bytes)
    submissions = state["submission_count"]
    reviewed = state["reviewed_count"]
    status = state["review_status"]
    if reviewed < submissions and status is not None:
        raise ValueError("STALE_LATEST_REVIEW")
    if submissions == 0 and reviewed != 0:
        raise ValueError("REVIEW_WITHOUT_SUBMISSION")

    events = state["observed_tool_calls"]
    review_positions = [i for i, name in enumerate(events)
                        if name == "review_submitted_financials"]
    last_review = review_positions[-1] if review_positions else -1
    reads_total = events.count("read_page")
    reads_at_review = events[:last_review + 1].count("read_page")
    return {
        "financial_submission": deepcopy(state["financial_submission"]),
        "submission_attempts": {"count": submissions},
        "review_state": {
            "reviewed_count": reviewed,
            "status": status,
            "page_reads": reads_total,
            "reads_at_review": reads_at_review,
        },
        "observed_tool_calls": list(events),
        "model_conversation_restored": False,
    }
