"""Evaluate tool-call ordering without claiming that an LLM fixed evidence."""


def assess_tool_sequence(tool_calls):
    """Report whether the agent followed the required investigation order.

    This assesses observed tool names, not tool arguments or figure accuracy.
    Accepted submissions still require server-side guards.
    """
    events = list(tool_calls)
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
