"""No-credit approval UI fixture. Never uses real SDK, models or private files."""
from types import SimpleNamespace

from approval_queue import prepare_approval_queue, decide_approval, approval_public_status
from investigation_checkpoint import document_fingerprint


class OfflineApprovalState:
    def get_interruptions(self):
        return ["synthetic_financial_submission"]

    def approve(self, item, always_approve=False):
        self.last_action = "APPROVED"

    def reject(self, item, always_reject=False, rejection_message=None):
        self.last_action = "REJECTED"


def start_offline_approval(pdf_bytes):
    state = OfflineApprovalState()
    result = SimpleNamespace(
        interruptions=["synthetic_financial_submission"],
        to_state=lambda: state,
    )
    return prepare_approval_queue(result, document_fingerprint(pdf_bytes))


def finish_offline_approval(queue, pdf_bytes, approved):
    decide_approval(queue, document_fingerprint(pdf_bytes), 0, approved)
    return approval_public_status(queue)
