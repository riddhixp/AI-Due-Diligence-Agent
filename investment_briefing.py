
import re
from report_quality import check_report_quality
from financial_summary import generate_financial_summary


def extract_diligence_questions(report):
    """Extract numbered questions from the existing workplan."""

    lines = str(report or "").splitlines()
    collecting = False
    questions = []

    for line in lines:
        text = line.strip()

        if text.lower().startswith("priority diligence workplan"):
            collecting = True
            continue

        if not collecting:
            continue

        if text.lower().startswith((
            "facts supported",
            "calculations based",
            "analyst inferences",
            "information materially unavailable",
            "evidence and limitations",
            "concluding recommendation",
        )):
            break

        match = re.match(r"^\d+[.)]\s+(.+)$", text)

        if match:
            questions.append(match.group(1).strip())
        elif text and questions:
            questions[-1] += " " + text

        if len(questions) >= 5:
            break

    return questions


def generate_investment_briefing(report, financial_data):
    """Assemble a preliminary, evidence-aware M&A briefing."""

    financial_insights = generate_financial_summary(
        financial_data
    )

    key_financial_insights = [
        insight for insight in financial_insights
        if insight["priority"] != "Financial evidence completion"
    ]

    missing_information = [
        insight for insight in financial_insights
        if insight["priority"] == "Financial evidence completion"
    ]

    quality_issues = check_report_quality(report)

    readiness = (
        "REQUIRES_REVIEW"
        if quality_issues
        else "NO_AUTOMATED_ISSUES_DETECTED"
    )

    return {
        "quality_issues": quality_issues,
        "readiness": readiness,
        "company": financial_data.get("company", "Company"),
        "fiscal_year": financial_data.get("fiscal_year"),
        "financial_priorities": key_financial_insights[:2],
        "diligence_questions": extract_diligence_questions(report),
        "evidence_gaps": missing_information,
        "disclaimer": (
            "Preliminary public-document due diligence. "
            "Financial figures, source citations and "
            "investment implications require human verification."
        ),
    }
