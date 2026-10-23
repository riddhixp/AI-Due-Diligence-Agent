"""Deterministic evaluation of a due diligence agent run.

For human QA and future controlled live-model evaluations. A passing score
does not prove autonomous reasoning or investment readiness.
"""
from agent_financial_review import review_financial_evidence
from investigation_outcome import investigation_outcome
from tool_sequence_audit import assess_tool_sequence


def evaluate_agent_run(pages, financial_data, tool_calls, submissions,
                       reviewed_count, review_status):
    """Evaluate observable, non-sensitive tool and evidence results."""
    tool_calls = list(tool_calls)
    evidence = (
        review_financial_evidence(pages, financial_data)
        if financial_data else {"status": "REVIEW_UNAVAILABLE"}
    )
    outcome = investigation_outcome(
        submissions, reviewed_count, review_status, tool_calls
    )
    sequence = assess_tool_sequence(tool_calls)

    latest_reviewed = outcome["latest_submission_reviewed"]
    evidence_passed = (
        evidence["status"] == "PRELIMINARY_CHECKS_PASSED"
        and latest_reviewed
    )
    issues = []
    if not latest_reviewed:
        issues.append("LATEST_SUBMISSION_NOT_REVIEWED")
    if not sequence["sequence_ok"]:
        issues.extend(sequence["issues"])
    if evidence["status"] != "PRELIMINARY_CHECKS_PASSED":
        issues.append("FINANCIAL_EVIDENCE_REQUIRES_REVIEW")
    if latest_reviewed and review_status != evidence["status"]:
        issues.append("REVIEW_STATUS_EVIDENCE_MISMATCH")

    return {
        "evaluation": "PRELIMINARY_PASS" if not issues and evidence_passed
                      else "NEEDS_HUMAN_REVIEW",
        "financial_evidence": evidence["status"],
        "investigation_outcome": outcome["outcome"],
        "sequence_ok": sequence["sequence_ok"],
        "issues": list(dict.fromkeys(issues)),
    }
