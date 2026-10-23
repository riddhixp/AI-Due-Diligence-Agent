"""Free deterministic reproduction of an interrupted financial investigation."""
from interrupted_report import interrupted_report
from investigation_checkpoint import create_checkpoint, document_fingerprint, inspect_checkpoint
from agent_evaluation import evaluate_agent_run
from synthetic_financial_fixture import supported_submission


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
    # Demo fingerprint derives from page text; this is not a model transcript.
    demo_bytes = "\\n".join(pages).encode("utf-8")
    checkpoint = create_checkpoint(
        document_fingerprint(demo_bytes), submitted, 1, 0, None, events
    )
    evaluation["checkpoint"] = {
        "compatible": inspect_checkpoint(checkpoint, demo_bytes)["compatible"],
        "resume_ready": False,
        "saved_submissions": checkpoint["submission_count"],
    }
    report = interrupted_report(submitted, 0, 1, None)
    report += (
        "\n\n**Scripted interruption demonstration only.** "
        "No AI model was run or resumed."
    )
    return report, None, submitted, evaluation
