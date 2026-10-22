"""Zero-credit, deterministic rehearsal for the synthetic conflicting PDF.

No model calls: this deliberately exercises the same financial review and
investigation evaluation functions with a scripted correction.
"""
from agent_financial_review import review_financial_evidence
from agent_evaluation import evaluate_agent_run
from financial_validator import FinancialData, validate_financials
from tests.test_investigation_scenarios import supported_submission


def simulate_conflict_correction(pages):
    if not any("SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY" in p for p in pages):
        raise ValueError("Offline demo supports only the synthetic conflict PDF.")
    if not any("Total revenue 120 100 90" in p for p in pages):
        raise ValueError("Authoritative fixture statement not found.")

    wrong = supported_submission()
    wrong["revenue_current"] = 130
    wrong["reported"]["revenue_growth"] = 30
    wrong["source_pages"] = dict.fromkeys(wrong["source_pages"], 2)
    initial = review_financial_evidence(pages, wrong)

    corrected = supported_submission()
    corrected["source_pages"] = dict.fromkeys(corrected["source_pages"], 2)
    final = review_financial_evidence(pages, corrected)

    trace = [
        "read_page", "submit_financial_data", "review_submitted_financials",
        "read_page", "submit_financial_data", "review_submitted_financials",
    ]
    evaluation = evaluate_agent_run(
        pages, corrected, trace, 2, 2, final["status"]
    )
    evaluation["simulation"] = True
    evaluation["initial_review_status"] = initial["status"]
    evaluation["api_calls"] = 0

    if initial["status"] != "NEEDS_REVIEW":
        raise ValueError("The simulated incorrect figure was not rejected.")
    if evaluation["evaluation"] != "PRELIMINARY_PASS":
        raise ValueError("The simulated correction failed.")

    report = (
        "# Offline demonstration — scripted, not autonomous AI\n\n"
        "## Executive assessment\n\n"
        "The management summary reports USD 130m revenue (PDF page 1), "
        "but the financial statement reports USD 120m (PDF page 2). "
        "The first simulated submission failed verification; a scripted "
        "source reread and corrected submission passed preliminary checks.\n\n"
        "## Financial and commercial assessment\n\n"
        "FY2025 revenue: USD 120m; FY2024 revenue: USD 100m; "
        "growth: 20%. Gross margin: 66.67%; net margin: 25% "
        "(PDF page 2).\n\n"
        "## Technology and operational assessment\n\n"
        "Security assurance and retention information are unavailable "
        "(PDF page 1).\n\n"
        "## Growth opportunities and key risks\n\n"
        "Recurring revenue quality and cash conversion need validation.\n\n"
        "## Priority diligence workplan\n\n"
        "Request retention cohorts, cash flows, capex and security reports.\n\n"
        "## Evidence and limitations\n\n"
        "**This is a scripted offline demonstration.** It does not "
        "demonstrate an AI agent reasoning or correcting autonomously."
    )
    return report, None, corrected, evaluation
