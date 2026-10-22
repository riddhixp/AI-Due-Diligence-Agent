"""Scripted continuation of a restored financial investigation (no model/API)."""
from copy import deepcopy
from financial_state_restore import restore_financial_state
from investigation_control import submission_block_reason
from agent_financial_review import review_financial_evidence
from correction_changes import financial_correction_changes
from agent_evaluation import evaluate_agent_run


def simulate_restored_continuation(checkpoint, pdf_bytes, pages, corrected_submission):
    state = restore_financial_state(checkpoint, pdf_bytes)
    if state["submission_count"] != 1:
        raise ValueError("EXPECTED_SINGLE_INITIAL_SUBMISSION")
    initial = deepcopy(state["financial_submission"])
    trace = state["observed_tool_calls"]
    reviewed_count = state["reviewed_count"]
    review_status = state["review_status"]

    # Finish the missing review, or respect the review already in checkpoint.
    if reviewed_count != 1:
        first = review_financial_evidence(pages, initial)
        review_status = first["status"]
        reviewed_count = 1
        trace.append("review_submitted_financials")
    if review_status != "NEEDS_REVIEW":
        raise ValueError("CORRECTION_NOT_REQUIRED")

    if submission_block_reason(1, reviewed_count, review_status, 0) is None:
        raise ValueError("EXPECTED_SOURCE_RECHECK_GUARD")
    trace.append("read_page")
    if submission_block_reason(1, reviewed_count, review_status, 1):
        raise ValueError("CORRECTION_BLOCKED")
    if not financial_correction_changes(initial, corrected_submission):
        raise ValueError("NO_CORRECTION_MADE")

    trace.append("submit_financial_data")
    corrected = deepcopy(corrected_submission)
    second = review_financial_evidence(pages, corrected)
    trace.append("review_submitted_financials")
    evaluation = evaluate_agent_run(pages, corrected, trace, 2, 2, second["status"])
    evaluation["simulation"] = True
    evaluation["api_calls"] = 0
    evaluation["conversation_restored"] = False
    return evaluation
