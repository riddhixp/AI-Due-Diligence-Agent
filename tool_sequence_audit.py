"""Evaluate tool-call ordering without claiming that an LLM fixed evidence."""


def assess_tool_sequence(tool_calls, *, observed_tool_calls=None):
    """Report whether the agent followed the required investigation order.

    This assesses observed tool names, not tool arguments or figure accuracy.
    Accepted submissions still require server-side guards.
    """
    events = list(tool_calls)
    if observed_tool_calls is not None:
        observed = list(observed_tool_calls)
        refused = observed.count("source_recheck_refused")
        if refused:
            # Only server-recorded source reread refusals are recoverable.
            # Other unaccepted requests retain the conservative audit failure.
            result = assess_tool_sequence(observed)
            attempted = events.count("submit_financial_data")
            accounted = observed.count("submit_financial_data") + refused
            if attempted != accounted:
                result["issues"].append("UNACCOUNTED_SUBMISSION_TOOL_CALLS")
                result["sequence_ok"] = False
            critical = {"read_page", "submit_financial_data", "review_submitted_financials"}
            aliases = {"source_recheck_refused": "submit_financial_data",
                       "review_without_submission": "review_submitted_financials"}
            recorded = [aliases.get(event, event) for event in observed]
            recorded = [event for event in recorded if event in critical]
            reported = [event for event in events if event in critical]
            if reported != recorded:
                result["issues"].append("TOOL_TRACE_MISMATCH")
                result["sequence_ok"] = False
            result["source_recheck_refusals"] = refused
            result["submission_attempts"] = attempted
            return result
    submissions = [i for i, name in enumerate(events)
                   if name == "submit_financial_data"]
    reviews = [i for i, name in enumerate(events)
               if name == "review_submitted_financials"]
    problems = []

    if not submissions:
        problems.append("NO_SUBMISSION_TOOL_CALL")
    if not reviews:
        problems.append("NO_REVIEW_TOOL_CALL")

    if submissions and not any(i > submissions[0] for i in reviews):
        problems.append("FIRST_SUBMISSION_NOT_FOLLOWED_BY_REVIEW")

    if len(submissions) > 2:
        problems.append("EXCESS_SUBMISSION_TOOL_CALLS")

    if len(submissions) >= 2:
        first, second = submissions[:2]
        between = events[first + 1:second]
        if "review_submitted_financials" not in between:
            problems.append("CORRECTION_WITHOUT_INTERVENING_REVIEW")
        last_review_offset = max(
            (i for i, name in enumerate(between)
             if name == "review_submitted_financials"),
            default=-1,
        )
        if last_review_offset >= 0 and "read_page" not in between[last_review_offset + 1:]:
            problems.append("NO_PAGE_READ_AFTER_REVIEW")

        if not any(i > second for i in reviews):
            problems.append("CORRECTION_NOT_FOLLOWED_BY_REVIEW")

    return {"sequence_ok": not problems, "issues": problems,
            "submissions_called": len(submissions),
            "reviews_called": len(reviews)}
