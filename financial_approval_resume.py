"""In-memory approval-to-resume orchestration, restricted to the offline model.

The real app rebuilds financial tool closures and enforces completion checks.
This is a scripted rehearsal, not evidence of autonomous model reasoning.
"""
from io import BytesIO
import threading

from investigation_checkpoint import document_fingerprint
from live_financial_approval_decision import decide_live_financial_pause
from live_financial_pause_handoff import SDKFinancialApprovalPaused
from scripted_offline_model import ScriptedOfflineModel
from tool_state_rebinding import prepare_tool_state

_claim_lock = threading.Lock()


def decide_and_resume_offline(handoff, pdf_bytes, approved, model):
    """Apply one explicit decision and dispatch the genuine app SDK resume path.

    Consume the handoff before SDK mutation. Failures require manual inspection;
    they are never retried automatically. State remains process-local only.
    """
    if type(model) is not ScriptedOfflineModel:
        raise ValueError("LIVE_RESUME_DISABLED")
    if type(approved) is not bool:
        raise ValueError("INVALID_APPROVAL_DECISION")
    if not isinstance(handoff, dict) or handoff.get("live_resume_enabled") is not False:
        raise ValueError("INVALID_OFFLINE_HANDOFF")
    checkpoint = handoff.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("MISSING_FINANCIAL_CHECKPOINT")
    if checkpoint.get("document_sha256") != document_fingerprint(pdf_bytes):
        raise ValueError("DOCUMENT_MISMATCH")
    prepare_tool_state(checkpoint, pdf_bytes)
    # Derive tool evidence from the bound PDF, never caller-supplied page text.
    from pypdf import PdfReader
    pages = [page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages]
    if not pages or not any(page.strip() for page in pages):
        raise ValueError("READABLE_PDF_REQUIRED")

    with _claim_lock:
        if handoff.get("status") != "AWAITING_APPROVAL":
            raise ValueError("APPROVAL_RESUME_ALREADY_CLAIMED")
        try:
            decide_live_financial_pause(handoff, pdf_bytes, approved)
        except Exception:
            handoff["status"] = "FAILED"
            raise
        handoff["status"] = "RESUMING_OFFLINE"

    try:
        from due_diligence_engine import run_due_diligence
        result = run_due_diligence(
            pages, restored_checkpoint=checkpoint, resume_pdf_bytes=pdf_bytes,
            sdk_resume_state=handoff["sdk_state"], offline_scripted_model=model,
            financial_approval_required=True, pause_pdf_bytes=pdf_bytes,
        )
    except SDKFinancialApprovalPaused as paused:
        handoff["status"] = "PAUSED_AGAIN"
        return {"status": "AWAITING_APPROVAL", "handoff": paused.handoff,
                "external_api_calls": 0, "scripted": True}
    except Exception:
        handoff["status"] = "FAILED"
        raise
    handoff["status"] = "COMPLETED_OFFLINE"
    report, validation, financial, evaluation = result
    evaluation["simulation"] = True
    return {"status": "COMPLETED_OFFLINE", "report": report,
            "validation": validation, "financial": financial,
            "evaluation": evaluation, "external_api_calls": 0, "scripted": True}
