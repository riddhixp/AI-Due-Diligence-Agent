"""Real SDK, scripted zero-network, financial correction UI demonstration."""
from io import BytesIO
from pypdf import PdfReader
from agents import Agent, Runner, function_tool
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from investigation_checkpoint import create_checkpoint, document_fingerprint
from tool_state_rebinding import prepare_tool_state
from investigation_control import submission_block_reason
from agent_financial_review import review_financial_evidence
from synthetic_financial_fixture import PAGES, supported_submission
from scripted_offline_model import ScriptedOfflineModel


def start_financial_resume_demo(pdf_bytes):
    try:
        pages = [(page.extract_text() or "") for page in PdfReader(BytesIO(pdf_bytes)).pages]
    except Exception as exc:
        raise ValueError("VALID_SYNTHETIC_CONFLICT_PDF_REQUIRED") from exc
    if (
        len(pages) != 2
        or "SYNTHETIC CONFLICT TEST - NOT A REAL COMPANY" not in pages[0]
        or "Total revenue 120 100 90" not in pages[1]
        or "The authoritative FY2025 total revenue figure is 120" not in pages[1]
    ):
        raise ValueError("SYNTHETIC_CONFLICT_PDF_REQUIRED")
    wrong = supported_submission()
    wrong["revenue_current"] = 130
    wrong["reported"]["revenue_growth"] = 30
    checkpoint = create_checkpoint(
        document_fingerprint(pdf_bytes), wrong, 1, 0, None,
        ["read_page", "submit_financial_data"],
    )
    financial = prepare_tool_state(checkpoint, pdf_bytes)
    trace = financial["observed_tool_calls"]
    review = financial["review_state"]
    counts = financial["submission_attempts"]
    corrected = supported_submission()
    model = ScriptedOfflineModel()
    model.responses = [
        [ResponseFunctionToolCall(id="f1", call_id="c1", type="function_call",
            name="review_submitted_financials", arguments="{}", status="completed")],
        [ResponseFunctionToolCall(id="f2", call_id="c2", type="function_call",
            name="read_page", arguments='{"page_number":1}', status="completed")],
        [ResponseFunctionToolCall(id="f3", call_id="c3", type="function_call",
            name="submit_financial_data", arguments='{"revenue":120}', status="completed")],
        [ResponseFunctionToolCall(id="f4", call_id="c4", type="function_call",
            name="review_submitted_financials", arguments="{}", status="completed")],
        [ResponseOutputMessage(id="m1", type="message", role="assistant",
            status="completed", content=[ResponseOutputText(
                type="output_text", text="Offline financial investigation completed.",
                annotations=[])])],
    ]

    @function_tool
    def review_submitted_financials() -> str:
        """Review evidence for the latest synthetic financial submission."""
        result = review_financial_evidence(PAGES, financial["financial_submission"])
        trace.append("review_submitted_financials")
        review["reviewed_count"] = counts["count"]
        review["status"] = result["status"]
        review["reads_at_review"] = review["page_reads"]
        return result["status"]

    @function_tool
    def read_page(page_number: int) -> str:
        """Read synthetic source page."""
        if page_number != 1:
            return "INVALID_PAGE"
        trace.append("read_page")
        review["page_reads"] += 1
        return PAGES[0]

    @function_tool(needs_approval=True)
    def submit_financial_data(revenue: float) -> str:
        """Submit synthetic corrected revenue only after a failed review and reread."""
        reason = submission_block_reason(
            counts["count"], review["reviewed_count"], review["status"],
            review["page_reads"] - review["reads_at_review"],
        )
        if reason:
            return reason
        if revenue != corrected["revenue_current"]:
            return "INVALID_TEST_REVENUE"
        financial["financial_submission"] = corrected.copy()
        counts["count"] += 1
        review["status"] = None
        trace.append("submit_financial_data")
        return "ACCEPTED"

    agent = Agent(name="Synthetic correction workflow", model=model,
        tools=[review_submitted_financials, read_page, submit_financial_data])
    first = Runner.run_sync(agent, "Synthetic financial review and correction")
    if len(first.interruptions) != 1 or review["status"] != "NEEDS_REVIEW":
        raise ValueError("EXPECTED_REVIEWED_CORRECTION_PAUSE")
    return {
        "sdk_state": first.to_state(), "agent": agent,
        "financial": financial, "pdf_hash": document_fingerprint(pdf_bytes),
        "status": "AWAITING_APPROVAL", "external_api_calls": 0,
    }


def finish_financial_resume_demo(session, pdf_bytes, approved):
    if session["pdf_hash"] != document_fingerprint(pdf_bytes):
        raise ValueError("DOCUMENT_MISMATCH")
    if session["status"] != "AWAITING_APPROVAL":
        raise ValueError("DECISION_ALREADY_MADE")
    if type(approved) is not bool:
        raise ValueError("INVALID_DECISION")
    session["status"] = "RESUMING"  # consumed before calling the SDK
    state = session["sdk_state"]
    interrupt = state.get_interruptions()[0]
    if approved:
        state.approve(interrupt)
    else:
        state.reject(interrupt, rejection_message="Offline financial correction rejected")
    output = Runner.run_sync(session["agent"], state)
    financial = session["financial"]
    review = financial["review_state"]
    submissions = financial["submission_attempts"]["count"]
    session["status"] = "COMPLETED"
    return {
        "decision": "APPROVED" if approved else "REJECTED",
        "finished": bool(output.final_output),
        "submissions": submissions,
        "reviewed": review["reviewed_count"],
        "review_status": review["status"],
        "corrected_revenue": financial["financial_submission"]["revenue_current"],
        "external_api_calls": 0,
        "scripted": True,
    }
