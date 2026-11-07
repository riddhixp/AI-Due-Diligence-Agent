
import re


REQUIRED_SECTIONS = [
    "Executive assessment",
    "Financial and commercial assessment",
    "Technology and operational assessment",
    "Growth opportunities and key risks",
    "Priority diligence workplan",
    "Evidence and limitations",
]

UNPROFESSIONAL_PHRASES = [
    "If you want, I can",
    "As an AI",
    "Developer rule",
    "I hope this helps",
]


def check_report_quality(report):
    """
    Check a due diligence report for common writing
    and structural problems.

    These are heuristic checks, not a substitute
    for professional editorial review.
    """

    issues = []
    report = str(report or "")

    if not report.strip():
        return ["The report is empty."]

    # Check that required sections are present.
    for section in REQUIRED_SECTIONS:
        if section.lower() not in report.lower():
            issues.append(
                f"Missing section: {section}"
            )

    # Detect mechanical labels at the start of lines.
    mechanical_pattern = (
        r"(?im)^\s*(?:[-*]\s*)?"
        r"(?:\d+[\.)]\s*)?"
        r"(?:finding|evidence|commercial implication|"
        r"further diligence)\s*[:\-–]"
    )

    if re.search(mechanical_pattern, report):
        issues.append(
            "Mechanical labels detected in the report."
        )

    # Detect unprofessional conversational phrases.
    for phrase in UNPROFESSIONAL_PHRASES:
        if phrase.lower() in report.lower():
            issues.append(
                f"Unprofessional phrase detected: {phrase}"
            )

    # Detect consecutive duplicate non-empty lines.
    previous_line = None

    for line in report.splitlines():
        clean_line = line.strip().lower()

        if not clean_line:
            continue

        if clean_line == previous_line:
            issues.append(
                f"Repeated consecutive line: {line.strip()}"
            )

        previous_line = clean_line

    # Check for unfinished placeholders.
    placeholder_pattern = (
        r"(?i)(?:\bTBD\b|\bTODO\b|\[insert[^\]]*\]|"
        r"(?<!\w)[<>]\s*X\s*%|\bX\s*%\s*\(specify)"
    )

    if re.search(placeholder_pattern, report):
        issues.append(
            "Unresolved placeholder detected."
        )

    # Check for a missing opening executive assessment.
    executive_match = re.search(
        r"(?im)^#{1,2}\s+Executive assessment\s*$",
        report,
    )

    if executive_match:
        after_heading = report[executive_match.end():]
        first_content = next(
            (line.strip() for line in after_heading.splitlines()
             if line.strip()),
            "",
        )

        if (
            not first_content
            or first_content.startswith(("1.", "1)", "-", "*", "##"))
        ):
            issues.append(
                "Executive assessment may be missing its opening conclusion."
            )

    # Detect unexpected sections in Markdown or plain-text reports.
    unexpected_sections = [
        "Concluding recommendation",
        "Final recommendation",
        "Investment recommendation",
        "Overall conclusion",
        "Conclusion and next steps",
    ]

    for line in report.splitlines():
        heading = re.sub(
            r"^\s*#{1,3}\s*",
            "",
            line,
        ).strip()

        for section in unexpected_sections:
            if re.match(
                rf"(?i)^{re.escape(section)}"
                r"(?:\s*$|\s*[\(\-–—:])",
                heading,
            ):
                issues.append(
                    f"Unexpected main section: {heading}"
                )
                break


    # Flag mechanical classification headings.
    classification_pattern = (
        r"(?im)^\s*(?:#{1,3}\s*)?"
        r"(?:facts supported by the filing|"
        r"calculations based on those facts|"
        r"analyst inferences that require validation|"
        r"information materially unavailable in the filing)"
        r"\s*(?:\(.*\))?\s*$"
    )

    if re.search(classification_pattern, report):
        issues.append(
            "Mechanical classification headings detected."
        )

    # Flag potentially overstated conclusions for human review.
    certainty_pattern = (
        r"(?i)\b(?:proven|guaranteed|risk-free|"
        r"durable|defensible)\b"
    )

    if re.search(certainty_pattern, report):
        issues.append(
            "Potentially overstated claim detected; review its evidence."
        )


    # Flag subscription durability claims for evidence review.
    if re.search(
        r"(?is)\b(?:subscription|recurring revenue)\b"
        r"[^\n.!?]{0,140}\b(?:durable|guaranteed|secure)\b",
        report,
    ) or re.search(
        r"(?is)\b(?:durable|guaranteed|secure)\b"
        r"[^\n.!?]{0,140}\b(?:subscription|recurring revenue)\b",
        report,
    ):
        issues.append(
            "Subscription durability claim requires evidence "
            "from retention, renewal or cohort-level data."
        )

    # Flag claims about how share repurchases were funded.
    repurchase_terms = (
        r"(?:share repurchases?|stock repurchases?|"
        r"share buybacks?|stock buybacks?)"
    )

    cash_flow_terms = (
        r"(?:operating cash flow|cash flow from operations|"
        r"cash generated from operations)"
    )

    funding_language = (
        r"(?:funded by|financed by|paid for by|"
        r"funded through|financed through)"
    )

    if re.search(
        rf"(?is){repurchase_terms}[^\n.!?]{{0,180}}"
        rf"{funding_language}[^\n.!?]{{0,100}}"
        rf"{cash_flow_terms}",
        report,
    ) or re.search(
        rf"(?is){cash_flow_terms}[^\n.!?]{{0,180}}"
        rf"{funding_language}[^\n.!?]{{0,100}}"
        rf"{repurchase_terms}",
        report,
    ):
        issues.append(
            "Share repurchase funding claim requires "
            "reconciliation to the complete cash-flow "
            "and financing statements."
        )

    # Flag numerical claims that may lack a source citation.
    # This checks citation presence, not source accuracy.
    source_pattern = re.compile(
        r"(?i)\b(?:pdf\s*p(?:ages?|\.)?\s*\.?\s*\d+|"
        r"pdf\s*pp\.\s*\d+|"
        r"source\s*:\s*page\s*\d+|"
        r"(?:\bpage\s+\d+\b))"
    )

    numeric_claim_pattern = re.compile(
        r"(?i)(?:[$£€]\s*\d[\d,]*(?:\.\d+)?|"
        r"\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*(?:bn|million|billion)\b)"
    )

    uncited_claims = []

    for paragraph in re.split(r"\n\s*\n", report):
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        if (
            numeric_claim_pattern.search(paragraph)
            and not source_pattern.search(paragraph)
        ):
            uncited_claims.append(paragraph[:100])

    if uncited_claims:
        issues.append(
            f"{len(uncited_claims)} numerical passage(s) "
            "may lack PDF source references."
        )

    return issues
