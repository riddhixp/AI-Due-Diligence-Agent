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
    # Do not rebuild privileged financial counters from an inconsistent trace.
    if events.count("submit_financial_data") != submissions:
        raise ValueError("SUBMISSION_TRACE_COUNT_MISMATCH")
    # reviewed_count identifies the most recently reviewed submission, not
    # the number of review invocations. Rechecking one submission is valid.
    traced_submissions = 0
    traced_reviewed = 0
    review_positions = []
    for index, name in enumerate(events):
        if name == "submit_financial_data":
            traced_submissions += 1
        elif name == "review_submitted_financials":
            if traced_submissions == 0:
                raise ValueError("REVIEW_BEFORE_SUBMISSION")
            traced_reviewed = traced_submissions
            review_positions.append(index)
    if traced_reviewed != reviewed:
        raise ValueError("REVIEW_TRACE_COUNT_MISMATCH")
    read_events = checkpoint.get("page_read_events", [])
    if not isinstance(read_events, list):
        raise ValueError("INVALID_PAGE_READ_HISTORY")
    previous_index = -1
    for event in read_events:
        if (not isinstance(event, dict) or set(event) != {"tool_index", "page"}
                or type(event["tool_index"]) is not int or type(event["page"]) is not int
                or not previous_index < event["tool_index"] < len(events)
                or event["page"] < 1
                or events[event["tool_index"]] != "read_page"):
            raise ValueError("INVALID_PAGE_READ_HISTORY")
        previous_index = event["tool_index"]
    last_review = review_positions[-1] if review_positions else -1
    reads_total = events.count("read_page")
    reads_at_review = events[:last_review + 1].count("read_page")
    return {
        "page_read_events": deepcopy(read_events),
        "financial_submission": deepcopy(state["financial_submission"]),
        "submission_attempts": {"count": submissions},
        "review_state": {
            "reviewed_count": reviewed,
            "status": status,
            "page_reads": reads_total,
            "reads_at_review": reads_at_review,
            "source_pages_since_review": {event["page"] for event in read_events
                                          if event["tool_index"] > last_review},
        },
        "observed_tool_calls": list(events),
        "model_conversation_restored": False,
    }
