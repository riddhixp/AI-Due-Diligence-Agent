"""Create a non-sensitive audit appendix for due diligence output."""


def append_audit_appendix(report, outcome, sequence):
    """Add a short, reproducible trace summary with no document contents."""
    report = str(report or "")
    heading = "## Agent investigation audit"
    if heading in report:
        return report

    issues = ", ".join(sequence.get("issues") or []) or "None flagged"
    outcome_label = outcome.get("outcome") or "UNKNOWN"
    reviewed = "Yes" if outcome.get("latest_submission_reviewed") else "No"
    sequence_ok = "Yes" if sequence.get("sequence_ok") else "No"
    appendix = (
        f"\n\n---\n\n{heading}\n\n"
        f"- Investigation outcome: `{outcome_label}`\n"
        f"- Accepted financial submissions: {outcome.get('submissions', 0)}\n"
        f"- Latest submission reviewed: {reviewed}\n"
        f"- Tool-call sequence follows expected order: {sequence_ok}\n"
        f"- Sequence warnings: {issues}\n\n"
        "This audit records tool sequencing and preliminary review state. "
        "It does not establish that the AI independently reasoned correctly "
        "or that the underlying financial data is audited.\n"
    )
    if sequence.get("source_recheck_refusals"):
        appendix += (
            f"\n- Financial submission requests: {sequence['submission_attempts']}\n"
            f"- Source-reread refusals: {sequence['source_recheck_refusals']}\n"
            "These refused requests did not replace the accepted figures or consume "
            "a successful correction slot.\n"
        )
    return report.rstrip() + appendix
