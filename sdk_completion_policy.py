"""Explicitly classify resumed SDK states before report completion.

An approval decision is not evidence that a model resumed or reviewed finances.
"""


def sdk_continuation_complete(evaluation, handoff=None):
    if not isinstance(evaluation, dict):
        return False
    if handoff is None:
        return True
    if not isinstance(handoff, dict):
        return False
    return (
        handoff.get("status") == "COMPLETED"
        and handoff.get("model_resumed") is True
        and handoff.get("financial_review_completed") is True
        and handoff.get("document_match") is True
    )
