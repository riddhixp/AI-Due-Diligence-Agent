"""Validate serialisable investigation checkpoints without claiming model resumption."""
import hashlib
import copy
import re


def document_fingerprint(pdf_bytes):
    return hashlib.sha256(pdf_bytes).hexdigest()


def create_checkpoint(document_sha256, financial_data, submission_count,
                      reviewed_count, review_status, tool_calls, *, page_read_events=None):
    """Save only minimal, non-secret structured state."""
    if not isinstance(document_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", document_sha256) is None:
        raise ValueError("Invalid document fingerprint")
    if (type(submission_count) is not int or type(reviewed_count) is not int
            or not 0 <= reviewed_count <= submission_count <= 2):
        raise ValueError("Invalid review counters")
    checkpoint = {
        "version": 1,
        "document_sha256": document_sha256,
        "financial_data": copy.deepcopy(dict(financial_data)),
        "submission_count": submission_count,
        "reviewed_count": reviewed_count,
        "review_status": review_status,
        "tool_calls": list(tool_calls),
        "model_conversation_saved": False,
    }
    if page_read_events is not None:
        checkpoint["page_read_events"] = [dict(event) for event in page_read_events]
    return checkpoint


def inspect_checkpoint(checkpoint, pdf_bytes):
    """Return an explicit compatibility and resume-readiness result."""
    if (not isinstance(checkpoint, dict) or type(checkpoint.get("version")) is not int
            or checkpoint["version"] != 1):
        return {"compatible": False, "can_resume": False, "reason": "UNSUPPORTED_CHECKPOINT"}
    if checkpoint.get("model_conversation_saved") is not False:
        return {"compatible": False, "can_resume": False, "reason": "INVALID_CHECKPOINT_CAPABILITIES"}
    if checkpoint.get("document_sha256") != document_fingerprint(pdf_bytes):
        return {"compatible": False, "can_resume": False, "reason": "DOCUMENT_MISMATCH"}
    return {
        "compatible": True,
        "can_resume": False,
        "reason": "MODEL_CONVERSATION_NOT_SAVED",
        "saved_submissions": checkpoint.get("submission_count", 0),
        "saved_reviews": checkpoint.get("reviewed_count", 0),
    }
