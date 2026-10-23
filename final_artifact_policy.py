"""Conservative final-report artifact policy.

Diagnostic JSON and progress summaries remain available. Final report export
and caching require observed verification, not just a model-produced narrative.
"""


def final_report_eligible(evaluation):
    if not isinstance(evaluation, dict):
        return False
    return (
        evaluation.get("evaluation") == "PRELIMINARY_PASS"
        and evaluation.get("financial_evidence") == "PRELIMINARY_CHECKS_PASSED"
        and evaluation.get("sequence_ok") is True
        and not evaluation.get("issues")
        and evaluation.get("final_eligible", True) is not False
        and evaluation.get("simulation") is not True
    )
