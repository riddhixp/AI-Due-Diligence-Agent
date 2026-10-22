"""Validate serialisable investigation checkpoints without claiming model resumption."""
import hashlib


def document_fingerprint(pdf_bytes):
    return hashlib.sha256(pdf_bytes).hexdigest()


def create_checkpoint(document_sha256, financial_data, submission_count,
                      reviewed_count, review_status, tool_calls):
    """Save only minimal, non-secret structured state."""
    if len(document_sha256) != 64:
        raise ValueError("Invalid document fingerprint")
    if submission_count < 0 or reviewed_count < 0 or reviewed_count > submission_count:
        raise ValueError("Invalid review counters")
    return {
        "version": 1,
        "document_sha256": document_sha256,
        "financial_data": dict(financial_data),
        "submission_count": submission_count,
        "reviewed_count": reviewed_count,
        "review_status": review_status,
        "tool_calls": list(tool_calls),
        "model_conversation_saved": False,
    }


def inspect_checkpoint(checkpoint, pdf_bytes):
    """Return an explicit compatibility and resume-readiness result."""
    if not isinstance(checkpoint, dict) or checkpoint.get("version") != 1:
        return {"compatible": False, "can_resume": False, "reason": "UNSUPPORTED_CHECKPOINT"}
    if checkpoint.get("document_sha256") != document_fingerprint(pdf_bytes):
        return {"compatible": False, "can_resume": False, "reason": "DOCUMENT_MISMATCH"}
    return {
        "compatible": True,
        "can_resume": False,
        "reason": "MODEL_CONVERSATION_NOT_SAVED",
        "saved_submissions": checkpoint.get("submission_count", 0),
        "saved_reviews": checkpoint.get("reviewed_count", 0),
    }
