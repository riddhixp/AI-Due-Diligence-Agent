"""Free deterministic reproduction of an interrupted financial investigation."""
from interrupted_report import interrupted_report
from agent_evaluation import evaluate_agent_run
from tests.test_investigation_scenarios import supported_submission


def simulate_turn_limit(pages):
    if not any("SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY" in str(p) for p in pages):
        raise ValueError("Interruption demo requires the synthetic conflict PDF.")
    submitted = supported_submission()
    submitted["revenue_current"] = 130
    submitted["reported"]["revenue_growth"] = 30
    submitted["source_pages"] = dict.fromkeys(submitted["source_pages"], 2)
    # Deliberately interrupt after the first accepted submission, before review.
    events = ["read_page", "submit_financial_data"]
    evaluation = evaluate_agent_run(pages, submitted, events, 1, 0, None)
    evaluation["evaluation"] = "INTERRUPTED_TURN_LIMIT"
    evaluation["issues"] = list(dict.fromkeys(
        evaluation["issues"] + ["AGENT_MAX_TURNS_EXCEEDED"]
    ))
    evaluation["simulation"] = True
    evaluation["api_calls"] = 0
    evaluation["can_resume"] = False
    report = interrupted_report(submitted, 0, 1, None)
    report += (
        "\n\n**Scripted interruption demonstration only.** "
        "No AI model was run or resumed."
    )
    return report, None, submitted, evaluation
