"""Restore deterministic investigation counters from a document-bound checkpoint.

This restores *Python validation state only*, not the OpenAI conversation.
"""
import copy
from investigation_checkpoint import inspect_checkpoint


def restore_financial_state(checkpoint, pdf_bytes):
    inspection = inspect_checkpoint(checkpoint, pdf_bytes)
    if not inspection["compatible"]:
        raise ValueError(inspection["reason"])

    submissions = checkpoint.get("submission_count")
    reviewed = checkpoint.get("reviewed_count")
    status = checkpoint.get("review_status")
    figures = checkpoint.get("financial_data")
    events = checkpoint.get("tool_calls")
    if (type(submissions) is not int or type(reviewed) is not int
            or not 0 <= reviewed <= submissions <= 2):
        raise ValueError("INVALID_SUBMISSION_COUNTERS")
    if status not in (None, "NEEDS_REVIEW", "PRELIMINARY_CHECKS_PASSED"):
        raise ValueError("INVALID_REVIEW_STATUS")
    if reviewed == 0 and status is not None:
        raise ValueError("STALE_REVIEW_STATUS")
    # A correction clears the latest status while retaining the earlier
    # reviewed submission count. Only a review of the latest figures needs
    # a status; earlier feedback cannot stand in for the pending review.
    if reviewed == submissions and reviewed > 0 and status is None:
        raise ValueError("MISSING_REVIEW_STATUS")
    if not isinstance(figures, dict) or not isinstance(events, list):
        raise ValueError("INVALID_CHECKPOINT_DATA")
    if not all(isinstance(x, str) for x in events):
        raise ValueError("INVALID_TOOL_EVENTS")
    if submissions == 0 and figures:
        raise ValueError("FIGURES_WITHOUT_SUBMISSION")
    if submissions > 0 and not figures:
        raise ValueError("MISSING_SUBMISSION")

    return {
        "financial_submission": copy.deepcopy(figures),
        "submission_count": submissions,
        "reviewed_count": reviewed,
        "review_status": status,
        "observed_tool_calls": list(events),
        "conversation_restored": False,
    }
