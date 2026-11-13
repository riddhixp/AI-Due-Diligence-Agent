"""Verify a previously prepared synthetic portfolio demo without any model calls.

Usage: python -m verify_portfolio_demo --directory demo-run
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.create_conflict_test_fixture import PAGE_ONE, PAGE_TWO
from synthetic_conflict_document import read_synthetic_conflict_pages

PDF_NAME = "synthetic_conflict_test.pdf"
CARD_NAME = "demo-card.md"
MANIFEST_NAME = "demo-manifest.json"


def verify_demo(directory):
    directory = Path(directory)
    manifest_path = directory / MANIFEST_NAME
    if not directory.is_dir() or manifest_path.is_symlink():
        raise ValueError("INVALID_DEMO_DIRECTORY")
    if not manifest_path.is_file() or manifest_path.stat().st_size > 4096:
        raise ValueError("INVALID_DEMO_MANIFEST")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict)
            or type(manifest.get("version")) is not int or manifest["version"] != 1
            or manifest.get("scope") != "SYNTHETIC_OFFLINE_DEMO_ONLY"
            or manifest.get("manual_streamlit_acceptance") != "NOT_RUN"
            or manifest.get("autonomous_model_validation") != "NOT_RUN"
            or type(manifest.get("external_api_calls")) is not int
            or manifest["external_api_calls"] != 0
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != {PDF_NAME, CARD_NAME}):
        raise ValueError("INVALID_DEMO_MANIFEST")

    for name, limit in ((PDF_NAME, 5000000), (CARD_NAME, 100000)):
        path = directory / name
        expected = manifest["files"][name]
        if (type(expected) is not str or len(expected) != 64
                or any(ch not in "0123456789abcdef" for ch in expected)
                or path.is_symlink() or not path.is_file()
                or path.stat().st_size > limit
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError("DEMO_ASSET_INTEGRITY_FAILED")

    pages = read_synthetic_conflict_pages((directory / PDF_NAME).read_bytes())
    if (len(pages) != 2 or not all(line in pages[0] for line in PAGE_ONE)
            or not all(line in pages[1] for line in PAGE_TWO)):
        raise ValueError("DEMO_PDF_EVIDENCE_MISMATCH")
    card = (directory / CARD_NAME).read_text(encoding="utf-8")
    if (not card.startswith("# AI Due Diligence Agent")
            or "USD 120 million (page 2)" not in card
            or "Human browser click-through | NOT RUN" not in card
            or "Live autonomous model evaluation | NOT RUN" not in card):
        raise ValueError("DEMO_CARD_CONTENT_MISMATCH")
    return {"status": "PASS", "integrity": "VERIFIED",
            "scope": "SYNTHETIC_OFFLINE_DEMO_ONLY",
            "external_api_calls": 0, "manual_streamlit_acceptance": "NOT_RUN",
            "autonomous_model_validation": "NOT_RUN"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_demo(args.directory)
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
