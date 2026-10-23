"""Prevent incomplete or unverified resumed investigations being treated as final."""
from interrupted_report import interrupted_report


def enforce_completion_boundary(report, financial_data, submission_count,
                                review_state, evaluation):
    """Return a safe report and whether saving/exporting as final is allowed."""
    status = evaluation.get("evaluation")
    reviewed = review_state.get("reviewed_count", 0)
    passed = (
        submission_count > 0
        and reviewed == submission_count
        and review_state.get("status") == "PRELIMINARY_CHECKS_PASSED"
        and status == "PRELIMINARY_PASS"
        and evaluation.get("financial_evidence") == "PRELIMINARY_CHECKS_PASSED"
        and evaluation.get("sequence_ok") is True
        and not evaluation.get("issues")
    )
    if passed:
        return {"report": report, "final_eligible": True, "reason": "PRELIMINARY_PASS"}
    summary = interrupted_report(
        financial_data, reviewed, submission_count, review_state.get("status"),
    )
    summary = summary.replace(
        "# Investigation interrupted — no final AI report",
        "# Investigation incomplete — no verified final AI report",
    ).replace(
        "The AI reached its configured turn limit before producing a final assessment. "
        "This is **not** a completed due diligence report.",
        "Financial evidence, review sequence, or investigation completion has "
        "not passed every required check. This is **not** a completed report.",
    )
    return {"report": summary, "final_eligible": False,
            "reason": status or "INVESTIGATION_UNVERIFIED"}
