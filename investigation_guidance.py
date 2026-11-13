"""Convert financial review failures into bounded investigation guidance."""


def investigation_next_actions(review):
    """Prioritise actionable evidence checks without inventing data."""
    if not review or review.get("status") == "REVIEW_UNAVAILABLE":
        return ["Submit available, supported financial figures before review."]

    if review.get("status") == "PRELIMINARY_CHECKS_PASSED":
        return [
            "Proceed with preliminary diligence; do not describe these checks "
            "as an audit or proof of earnings quality."
        ]

    actions = []
    for name, check in (review.get("arithmetic") or {}).items():
        if check.get("status") != "PASS":
            actions.append(
                f"Recalculate {name} using the cited statement values; "
                "do not adjust source values to force an arithmetic pass."
            )

    for check in review.get("statement_checks") or []:
        if check.get("status") != "ROW_YEAR_MATCH":
            actions.append(
                f"Reopen the cited financial statement for "
                f"{check.get('metric', 'the relevant metric')} and verify "
                "its row label and fiscal-year column."
            )

    if any(item.get("Result") != "NUMBER_FOUND"
           for item in review.get("sources") or []):
        actions.append(
            "Check the PDF page references for figures not found on their "
            "cited pages; treat unresolved mismatches as unverified."
        )

    if review.get("metadata_issues"):
        actions.append(
            "Locate a source disclosure specifying currency and monetary "
            "scale; if absent, retain 'unspecified' and disclose the limitation."
        )

    return list(dict.fromkeys(actions)) or [
        "Review unresolved financial evidence manually and disclose uncertainty."
    ]
