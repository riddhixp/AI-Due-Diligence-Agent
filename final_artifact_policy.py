from sdk_completion_policy import sdk_continuation_complete

"""Conservative final-report artifact policy.

Diagnostic JSON and progress summaries remain available. Final report export
and caching require observed verification, not just a model-produced narrative.
"""


def final_report_eligible(evaluation, sdk_handoff=None):
    if not isinstance(evaluation, dict):
        return False
    return (
        sdk_continuation_complete(evaluation, sdk_handoff)
        and evaluation.get("evaluation") == "PRELIMINARY_PASS"
        and evaluation.get("financial_evidence") == "PRELIMINARY_CHECKS_PASSED"
        and evaluation.get("sequence_ok") is True
        and not evaluation.get("issues")
        and evaluation.get("final_eligible") is True
        and evaluation.get("simulation") is False
    )
