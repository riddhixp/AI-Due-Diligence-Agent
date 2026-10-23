"""Enforce evidence-review sequencing for financial submissions."""


def submission_block_reason(count, reviewed_count, review_status, pages_read_since_review=0):
    """Return a refusal message or None if a submission is permitted.

    Only one corrected submission is allowed, and only after the latest
    submitted figures have been reviewed and marked NEEDS_REVIEW.
    """
    if count >= 2:
        return "SUBMISSION_LIMIT_REACHED: Maximum of two successful submissions."

    if count == 1:
        if reviewed_count != count:
            return (
                "REVIEW_REQUIRED: Call review_submitted_financials "
                "before attempting a correction."
            )
        if review_status != "NEEDS_REVIEW":
            return (
                "CORRECTION_NOT_PERMITTED: The previous submission "
                "was not marked NEEDS_REVIEW."
            )
        if pages_read_since_review < 1:
            return (
                "SOURCE_RECHECK_REQUIRED: Read a relevant PDF page after "
                "the failed review before submitting a correction."
            )

    return None
