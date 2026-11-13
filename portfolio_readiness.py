"""Read-only release gates for the AI due diligence portfolio demo.

Runs the existing free synthetic fixture and network-guarded scripted acceptance.
Optionally verifies a prepared synthetic demo package before a local walkthrough.
Never starts paid analysis, opens a browser, or asserts manual approval.

Usage:
  python -m portfolio_readiness
  python -m portfolio_readiness --directory demo-run
"""
import argparse
import json
import sys
from pathlib import Path

from offline_demo_preflight import check_demo_fixture, check_demo_workflow
from portfolio_demo_card import render_demo_card
from verify_portfolio_demo import verify_demo


def assess_readiness(fixture, workflow, package=None):
    """Produce an evidence-bounded status; never infer unperformed checks."""
    # Reuse the strict evidence contract of the existing demo card.
    render_demo_card(fixture, workflow)
    package_status = "NOT_CHECKED"
    if package is not None:
        if (not isinstance(package, dict)
                or package.get("status") != "PASS"
                or package.get("integrity") != "VERIFIED"
                or package.get("scope") != "SYNTHETIC_OFFLINE_DEMO_ONLY"
                or type(package.get("external_api_calls")) is not int
                or package["external_api_calls"] != 0
                or package.get("manual_streamlit_acceptance") != "NOT_RUN"
                or package.get("autonomous_model_validation") != "NOT_RUN"):
            raise ValueError("INVALID_PORTFOLIO_PACKAGE_EVIDENCE")
        package_status = "VERIFIED"
    return {
        "status": "OFFLINE_REHEARSAL_READY",
        "scope": "SYNTHETIC_OFFLINE_ONLY",
        "automated_fixture": "PASS",
        "scripted_workflow": "PASS",
        "workflow_checks": workflow["workflow_checks"],
        "failure_scenarios": workflow["failure_scenarios"],
        "external_api_calls": 0,
        "demo_package_integrity": package_status,
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", type=Path,
        help="Verify an existing synthetic demo package and its manifest")
    args = parser.parse_args(argv)
    try:
        fixture = check_demo_fixture()
        workflow = check_demo_workflow()
        package = verify_demo(args.directory) if args.directory is not None else None
        result = assess_readiness(fixture, workflow, package)
    except Exception as error:
        # Do not print exception details, possibly containing extracted text.
        print(json.dumps({
            "status": "BLOCKED",
            "stage": "offline_checks_or_package_integrity",
            "error_type": type(error).__name__,
            "production_ready": False,
            "portfolio_demo_fully_validated": False,
        }))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
