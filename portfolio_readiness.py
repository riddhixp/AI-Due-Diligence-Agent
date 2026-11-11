"""Read-only release gates for the AI due diligence portfolio demo.

Runs the existing free synthetic fixture and network-guarded scripted acceptance.
Never starts the paid analysis, opens a browser, or asserts manual approval.
Usage: python -m portfolio_readiness
"""
import json
import sys

from offline_demo_preflight import check_demo_fixture, check_demo_workflow
from portfolio_demo_card import render_demo_card


def assess_readiness(fixture, workflow):
    """Produce an evidence-bounded status; never infer unperformed checks."""
    # Reuse the strict evidence contract of the existing demo card.
    render_demo_card(fixture, workflow)
    return {
        "status": "OFFLINE_REHEARSAL_READY",
        "scope": "SYNTHETIC_OFFLINE_ONLY",
        "automated_fixture": "PASS",
        "scripted_workflow": "PASS",
        "workflow_checks": workflow["workflow_checks"],
        "failure_scenarios": workflow["failure_scenarios"],
        "external_api_calls": 0,
        "manual_browser_acceptance": "NOT_RUN",
        "autonomous_model_validation": "NOT_RUN",
        "paid_continuation": "DISABLED",
        "production_ready": False,
        "portfolio_demo_fully_validated": False,
        "next_actions": [
            "Complete the manual Streamlit checklist in OFFLINE_DEMO.md.",
            "Verify current GitHub CI status for the feature branch.",
            "Require separate explicit approval before any paid-model test.",
        ],
    }


def main():
    try:
        result = assess_readiness(check_demo_fixture(), check_demo_workflow())
    except Exception as error:
        # Do not print exception details, potentially containing extracted text.
        print(json.dumps({
            "status": "BLOCKED",
            "stage": "offline_checks",
            "error_type": type(error).__name__,
            "production_ready": False,
            "portfolio_demo_fully_validated": False,
        }))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
