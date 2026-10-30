"""Classify an agent's financial verification and correction outcome."""


def investigation_outcome(submissions, reviewed_count, review_status, tool_calls):
    """Return deterministic, audit-friendly investigation status.

    A review status is only current if it belongs to the latest submission.
    Tool presence alone is not proof of a successful correction.
    """
    tool_calls = list(tool_calls)
    reviewed_latest = (
        submissions > 0
        and reviewed_count == submissions
        and review_status in ("NEEDS_REVIEW", "PRELIMINARY_CHECKS_PASSED")
    )

    if submissions == 0:
        outcome = "NO_FINANCIAL_SUBMISSION"
    elif not reviewed_latest:
        outcome = "LATEST_SUBMISSION_UNREVIEWED"
    elif submissions == 2 and review_status == "PRELIMINARY_CHECKS_PASSED":
        outcome = "CORRECTION_PASSED_PRELIMINARY_CHECKS"
    elif submissions == 2:
        outcome = "CORRECTION_STILL_NEEDS_REVIEW"
    elif review_status == "NEEDS_REVIEW":
        outcome = "INITIAL_SUBMISSION_NEEDS_REVIEW"
    else:
        outcome = "INITIAL_SUBMISSION_PASSED_PRELIMINARY_CHECKS"

    return {
        "outcome": outcome,
        "submissions": submissions,
        "latest_review_status": review_status if reviewed_latest else None,
        "latest_submission_reviewed": reviewed_latest,
        "page_reads": tool_calls.count("read_page"),
        "review_calls": tool_calls.count("review_submitted_financials"),
        "correction_attempted": submissions == 2,
    }
