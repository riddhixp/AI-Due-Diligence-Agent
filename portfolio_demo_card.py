"""Create a human-readable, evidence-bounded card for the free portfolio demo.

This command runs ONLY synthetic fixture checks and network-guarded scripted
acceptance. It never invokes the live analysis or paid model path.

Usage: python -m portfolio_demo_card --output demo-card.md
"""
import argparse
import json
import sys
from pathlib import Path

from offline_demo_preflight import check_demo_fixture, check_demo_workflow


def render_demo_card(fixture, workflow):
    """Fail closed unless both synthetic checks have explicit passing evidence."""
    if (not isinstance(fixture, dict) or fixture.get("status") != "PASS"
            or fixture.get("execution_mode") != "LOCAL_SYNTHETIC_FIXTURE_ONLY"
            or type(fixture.get("pages")) is not int or fixture["pages"] != 2
            or type(fixture.get("expected_authoritative_page")) is not int
            or fixture["expected_authoritative_page"] != 2
            or type(fixture.get("expected_revenue_millions")) is not int
            or fixture["expected_revenue_millions"] != 120
            or type(fixture.get("model_calls")) is not int
            or fixture["model_calls"] != 0
            or fixture.get("manual_streamlit_acceptance") != "NOT_RUN"
            or not isinstance(workflow, dict)
            or workflow.get("status") != "PASS"
            or workflow.get("execution_mode") != "SCRIPTED_OFFLINE_NETWORK_GUARDED"
            or type(workflow.get("workflow_checks")) is not int
            or workflow["workflow_checks"] < 1
            or type(workflow.get("failure_scenarios")) is not int
            or workflow["failure_scenarios"] < 1
            or type(workflow.get("external_api_calls")) is not int
            or workflow["external_api_calls"] != 0
            or workflow.get("autonomous_model_validation") != "NOT_RUN"
            or workflow.get("manual_streamlit_acceptance") != "NOT_RUN"):
        raise ValueError("INVALID_PORTFOLIO_DEMO_EVIDENCE")

    return (
        "# AI Due Diligence Agent — free demo verification card\n\n"
        "**Scope:** deterministic synthetic PDF, scripted SDK workflow, "
        "and network-guarded tests. No paid model calls.\n\n"
        "| Verification item | Observed result |\n"
        "| --- | --- |\n"
        "| Synthetic PDF fixture | PASS (2 pages) |\n"
        "| Misleading provisional revenue | USD 130 million (page 1) |\n"
        "| Authoritative revenue | USD 120 million (page 2) |\n"
        f"| Scripted workflow checks | {workflow['workflow_checks']} |\n"
        f"| Scripted failure scenarios | {workflow['failure_scenarios']} |\n"
        "| External model API calls in scripted checks | 0 |\n"
        "| Human browser click-through | NOT RUN |\n"
        "| Live autonomous model evaluation | NOT RUN |\n\n"
        "## What this verifies\n\n"
        "The supplied synthetic case and its scripted approval, correction, "
        "rejection, and failure controls passed the offline preflight. "
        "These checks test software behaviour, not the reliability of model reasoning.\n\n"
        "## Remaining verification\n\n"
        "- Complete manual Streamlit browser acceptance using OFFLINE_DEMO.md.\n"
        "- Validate autonomous analysis only after separate cost and provider approval.\n"
        "- Review security and privacy controls before using confidential deal documents.\n\n"
        "**Not an audited diligence conclusion, final investment report, "
        "or production certification.**\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        help="Create a new Markdown verification card; never overwrite")
    args = parser.parse_args(argv)
    try:
        fixture = check_demo_fixture()
        workflow = check_demo_workflow()
        card = render_demo_card(fixture, workflow)
    except Exception as error:
        print(json.dumps({"status": "FAIL", "stage": "offline_checks",
                          "error_type": type(error).__name__}))
        return 1

    if args.output is not None:
        created = False
        try:
            with args.output.open("x", encoding="utf-8") as handle:
                created = True
                handle.write(card)
        except OSError as error:
            if created:
                try:
                    args.output.unlink()
                except OSError:
                    pass
            print(json.dumps({"status": "FAIL", "stage": "output",
                              "error_type": type(error).__name__}))
            return 1
    print(card, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
