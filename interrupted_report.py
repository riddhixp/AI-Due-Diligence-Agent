"""Construct an honest partial report when a model run exceeds its turn cap."""


def interrupted_report(financial_data, reviewed_count, submissions, review_status):
    """No fabricated agent findings or implied final review."""
    reviewed = bool(
        submissions and reviewed_count == submissions
        and review_status in ("NEEDS_REVIEW", "PRELIMINARY_CHECKS_PASSED")
    )
    lines = [
        "# Investigation interrupted — no final AI report",
        "",
        "The AI reached its configured turn limit before producing a final "
        "assessment. This is **not** a completed due diligence report.",
        "",
        "## Progress preserved",
        "",
        f"- Accepted financial submissions: {submissions}",
        f"- Latest submission reviewed: {'Yes' if reviewed else 'No'}",
        f"- Latest review status: {review_status if reviewed else 'Unavailable or stale'}",
    ]
    if financial_data:
        lines.extend([
            f"- Submitted FY revenue: {financial_data.get('revenue_current', 'not available')}",
            f"- Submitted prior-year revenue: {financial_data.get('revenue_previous', 'not available')}",
        ])
    lines.extend([
        "",
        "## Next steps",
        "",
        "Review the evidence and any unresolved issues. Do not treat "
        "submitted numbers as verified unless the latest review passed. "
        "An additional API run may incur charges.",
    ])
    return "\n".join(lines)
