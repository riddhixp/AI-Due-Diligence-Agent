"""Attach deterministic evidence limitations to downloadable DD narratives.

These safeguards are based on the final observed verification state, not the
model's claims about whether its findings are verified.
"""

from verification_notice import final_verification_notice


def finalise_dd_report(report, financial_data, review):
    """Prepend a verification summary that survives Markdown/PDF export."""
    level, message = final_verification_notice(financial_data, review)
    status = review.get("status") if isinstance(review, dict) else None

    if status == "PRELIMINARY_CHECKS_PASSED" and financial_data:
        label = "Preliminary checks passed"
    elif level == "warning":
        label = "Financial evidence not fully verified"
    else:
        label = "Verification status uncertain"

    preface = (
        "## Evidence verification status\n\n"
        f"**{label}.** {message}\n\n"
        "This assessment is preliminary and requires human validation "
        "before use in an investment decision.\n\n"
        "---\n\n"
    )
    report = str(report or "")
    # Stable, idempotent output: calling twice does not produce two banners.
    if report.startswith("## Evidence verification status\n"):
        return report
    return preface + report
