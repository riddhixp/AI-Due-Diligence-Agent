"""Prevent a resumed run from promoting unreviewed finances to verified status."""
from agent_financial_review import review_financial_evidence


def trusted_latest_review(pages, financial_data, submission_count, review_state):
    """Only a matching, completed latest review may qualify for a pass."""
    if (not financial_data or submission_count < 1
            or review_state.get("reviewed_count") != submission_count
            or review_state.get("status") != "PRELIMINARY_CHECKS_PASSED"):
        return None
    result = review_financial_evidence(pages, financial_data)
    if result.get("status") != "PRELIMINARY_CHECKS_PASSED":
        return None
    return result
