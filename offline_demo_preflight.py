"""Check the offline demo fixture locally without running an AI model.

Usage: python -m offline_demo_preflight
The fixture is generated in a temporary directory and never uploaded.
"""
import argparse
import json
import tempfile
from pathlib import Path

from scripts.create_conflict_test_fixture import create_conflict_fixture, PAGE_ONE, PAGE_TWO
from synthetic_conflict_document import read_synthetic_conflict_pages


def check_demo_fixture():
    with tempfile.TemporaryDirectory() as folder:
        path = create_conflict_fixture(Path(folder) / "synthetic_conflict_test.pdf")
        pdf_bytes = path.read_bytes()
        pages = read_synthetic_conflict_pages(pdf_bytes)

    # The authoritative value must be on page 2; the misleading headline
    # must not be treated as authoritative. No model or network calls occur.
    if len(pages) != 2:
        raise ValueError("SYNTHETIC_FIXTURE_MISSING_PAGES")
    # Require every expected line on its intended page, rather than accepting
    # incidental number substrings elsewhere in the document.
    if (not all(line in pages[0] for line in PAGE_ONE)
            or not all(line in pages[1] for line in PAGE_TWO)):
        raise ValueError("SYNTHETIC_FIXTURE_CONTENT_CHANGED")
    return {
        "status": "PASS",
        "execution_mode": "LOCAL_SYNTHETIC_FIXTURE_ONLY",
        "pages": len(pages),
        "expected_authoritative_page": 2,
        "expected_revenue_millions": 120,
        "model_calls": 0,
        "manual_streamlit_acceptance": "NOT_RUN",
    }


def check_demo_workflow():
    """Run both scripted engine suites under the existing network guard."""
    from offline_acceptance import run_acceptance, acceptance_summary
    report = run_acceptance()
    if not acceptance_summary(report).startswith("Offline acceptance: PASS\\n"):
        raise ValueError("OFFLINE_DEMO_WORKFLOW_FAILED")
    suites = report["suites"]
    return {
        "status": "PASS",
        "execution_mode": "SCRIPTED_OFFLINE_NETWORK_GUARDED",
        "workflow_checks": len(suites["workflow"]["checks"]),
        "failure_scenarios": len(suites["failure_practice"]["scenarios"]),
        "external_api_calls": 0,
        "autonomous_model_validation": "NOT_RUN",
        "manual_streamlit_acceptance": "NOT_RUN",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", action="store_true",
                        help="Also run network-guarded scripted approval/correction checks")
    args = parser.parse_args(argv)
    try:
        result = check_demo_fixture()
        if args.workflow:
            result["workflow"] = check_demo_workflow()
    except Exception as error:
        # Do not include exception text or PDF contents in console output.
        print(json.dumps({"status": "FAIL", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
