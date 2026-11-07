"""Explicit opt-in fault injection, restricted to a synthetic test document."""


def inject_first_submission_error(submission, pages, *, enabled, accepted_count):
    """Return (possibly modified copy, injected).

    Never modify authentic filings. The injected figure is intentionally
    wrong so the agent can investigate and correct it through normal tools.
    """
    output = dict(submission)
    synthetic = any(
        "SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY" in str(page)
        for page in pages
    )
    if not (enabled and synthetic and accepted_count == 0):
        return output, False
    if output.get("revenue_current") != 120:
        return output, False
    output["revenue_current"] = 130
    return output, True
