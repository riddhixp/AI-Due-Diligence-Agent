"""Interpret the final verification state for human reviewers."""


def final_verification_notice(financial_data, review):
    """Return a severity and human-readable final-status explanation."""
    if not financial_data:
        return (
            "warning",
            "No structured financial submission was accepted. "
            "Financial figures in the narrative remain unverified.",
        )

    if not review or review.get("status") == "REVIEW_UNAVAILABLE":
        return (
            "warning",
            "Financial evidence review is unavailable; do not treat "
            "arithmetic checks as source verification.",
        )

    if review.get("status") != "PRELIMINARY_CHECKS_PASSED":
        problems = review.get("metadata_issues") or []
        suffix = " " + " ".join(problems) if problems else ""
        return (
            "warning",
            "Financial evidence requires further review. "
            "Do not rely on financial conclusions without checking "
            "statement rows, years and citations." + suffix,
        )

    return (
        "info",
        "Preliminary arithmetic and statement-source checks passed. "
        "This is not a full financial audit or proof of earnings quality.",
    )
