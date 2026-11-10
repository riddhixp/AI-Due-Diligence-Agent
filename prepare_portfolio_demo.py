"""Prepare the zero-credit portfolio demo assets together without running a model.

Usage: python -m prepare_portfolio_demo --directory /path/to/empty/folder

Requires an existing directory. Generates a fresh synthetic PDF and Markdown
verification card; never overwrites existing files or calls a paid provider.
"""
import argparse
import json
import tempfile
from pathlib import Path

from offline_demo_preflight import check_demo_fixture, check_demo_workflow
from portfolio_demo_card import render_demo_card
from scripts.create_conflict_test_fixture import create_conflict_fixture, PAGE_ONE, PAGE_TWO
from synthetic_conflict_document import read_synthetic_conflict_pages


def prepare_demo(directory):
    """Run guarded tests before creating either deliverable; roll back failures."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("OUTPUT_DIRECTORY_REQUIRED")
    pdf_target = directory / "synthetic_conflict_test.pdf"
    card_target = directory / "demo-card.md"
    # Do not overwrite either file; validate both targets before the costly checks.
    if pdf_target.exists() or card_target.exists():
        raise FileExistsError("DEMO_OUTPUT_ALREADY_EXISTS")

    fixture = check_demo_fixture()
    workflow = check_demo_workflow()
    card = render_demo_card(fixture, workflow)

    with tempfile.TemporaryDirectory() as folder:
        staged_pdf = create_conflict_fixture(Path(folder) / "synthetic_conflict_test.pdf")
        pdf_bytes = staged_pdf.read_bytes()
    # Verify the exact staged asset, not only the separately tested fixture.
    # A valid PDF header alone cannot prove the conflicting statements exist.
    try:
        pages = read_synthetic_conflict_pages(pdf_bytes)
        valid_pages = (
            len(pages) == 2
            and all(line in pages[0] for line in PAGE_ONE)
            and all(line in pages[1] for line in PAGE_TWO)
        )
    except Exception:
        valid_pages = False
    if not pdf_bytes.startswith(b"%PDF-") or not valid_pages:
        raise ValueError("INVALID_SYNTHETIC_DEMO_PDF")

    created = []
    try:
        # Exclusive creation ensures concurrent invocations do not silently
        # replace one another's evidence. Only files created here are removed.
        with pdf_target.open("xb") as handle:
            created.append(pdf_target)
            handle.write(pdf_bytes)
        with card_target.open("x", encoding="utf-8") as handle:
            created.append(card_target)
            handle.write(card)
    except OSError:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        raise

    return {
        "status": "PASS",
        "synthetic_pdf": pdf_target.name,
        "verification_card": card_target.name,
        "external_api_calls": 0,
        "manual_streamlit_acceptance": "NOT_RUN",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("."),
                        help="Existing directory for new synthetic demo assets")
    args = parser.parse_args(argv)
    try:
        result = prepare_demo(args.directory)
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
