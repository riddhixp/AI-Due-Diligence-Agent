
import os
import re
from agent_financial_review import review_financial_evidence
from optional_financial_validation import validate_optional_financial_data
from investigation_control import submission_block_reason
from investigation_outcome import investigation_outcome
from investigation_guidance import investigation_next_actions
from tool_sequence_audit import assess_tool_sequence
from verification_notice import final_verification_notice
from report_verification import finalise_dd_report
from audit_appendix import append_audit_appendix
from agent_evaluation import evaluate_agent_run
from run_limits import permitted_turn_limit
from cache_policy import should_cache_report
from correction_changes import financial_correction_changes
from revenue_narrative_check import find_reversed_revenue_arrows
from fault_injection import inject_first_submission_error
from interrupted_report import interrupted_report
from resume_transcript import extract_resume_input, inspect_replay_boundary
from sdk_resume_policy import classify_run_boundary
from sdk_pause_capture import capture_approval_pause, pause_public_status
from tool_state_rebinding import prepare_tool_state
from sdk_resume_gate import checked_resume_mode
from live_financial_pause_handoff import make_financial_pause_handoff, SDKFinancialApprovalPaused
from live_financial_approval_decision import decide_live_financial_pause
from live_continuation_preflight import preflight_live_continuation
from latest_review_gate import trusted_latest_review
from offline_demo import simulate_conflict_correction
from offline_interruption_demo import simulate_turn_limit
from offline_approval_demo import start_offline_approval, finish_offline_approval
from sdk_offline_approval_demo import start_sdk_offline_approval, decide_sdk_offline_approval, resume_sdk_offline_approval
from full_financial_resume_demo import start_financial_resume_demo, finish_financial_resume_demo
from pdf_report import generate_pdf_report
from report_quality import check_report_quality
from financial_metric_labels import verify_metric_automatically
from financial_labels import verify_revenue_automatically
from column_detector import verify_value_by_year
from source_verifier import (
    verify_financial_data,
    check_statement_row_and_year,
    verify_with_alternative_labels,
)
from source_verifier import (
    verify_financial_data,
    check_statement_row_and_year,
)
from io import BytesIO

import streamlit as st
from report_storage import save_report, load_report
from dotenv import load_dotenv
from pypdf import PdfReader
from financial_validator import FinancialData, validate_financials
from financial_insights import (
    ExtendedFinancialData,
    calculate_financial_insights,
)
from financial_summary import generate_financial_summary
from agents import (
    Agent,
    Runner,
    function_tool,
    set_tracing_disabled,
)

load_dotenv()
set_tracing_disabled(True)

st.set_page_config(
    page_title="AI Due Diligence Analyst",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AI Due Diligence Analyst")
st.caption(
    "Automated financial and technology due diligence"
)

st.warning(
    "Prototype: AI findings require human verification. "
    "Do not upload confidential client documents."
)


# -----------------------------
# Document processing
# -----------------------------

def extract_pages(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))

    if reader.is_encrypted:
        try:
            result = reader.decrypt("")
            if result == 0:
                raise ValueError(
                    "This PDF requires a password."
                )
        except Exception as error:
            raise ValueError(
                "Unable to unlock PDF without a password."
            ) from error

    return [
        (page.extract_text() or "").replace("\x00", "")
        for page in reader.pages
    ]



def find_evidence(pages, query, limit=5):
    """Find relevant PDF pages using phrase and keyword matching."""

    query = str(query or "").strip().lower()
    words = [
        word for word in re.findall(r"[a-z0-9]+", query)
        if len(word) > 2
    ]

    if not words:
        return []

    phrase = " ".join(words)
    results = []

    for number, content in enumerate(pages, start=1):
        if not content:
            continue

        lower = content.lower()

        # Normalise whitespace for phrase matching.
        normalised = re.sub(r"\s+", " ", lower)

        phrase_matches = normalised.count(phrase)
        distinct_matches = sum(
            1 for word in set(words) if word in lower
        )

        frequency = sum(
            min(lower.count(word), 10)
            for word in set(words)
        )

        score = (
            phrase_matches * 100
            + distinct_matches * 5
            + frequency
        )

        if score == 0:
            continue

        # Anchor the excerpt near a relevant phrase or keyword.
        positions = [
            lower.find(word)
            for word in words
            if lower.find(word) >= 0
        ]

        position = min(positions) if positions else 0
        start = max(0, position - 400)
        end = min(len(content), position + 1600)

        results.append(
            (score, number, content[start:end])
        )

    results.sort(
        key=lambda item: (-item[0], item[1])
    )

    return results[:limit]



# -----------------------------
# AI agent
# -----------------------------

def run_due_diligence(
    pages, max_turns=None, inject_test_error=False,
    restored_checkpoint=None, resume_pdf_bytes=None,
    financial_approval_required=False,
    sdk_resume_state=None, offline_scripted_model=None,
    pause_pdf_bytes=None,
):
    # Validate before any model call. Real paid SDK resumption is disabled.
    resume_mode = checked_resume_mode(
        restored_checkpoint, resume_pdf_bytes,
        sdk_resume_state, offline_scripted_model,
    )
    if restored_checkpoint is not None:
        if resume_pdf_bytes is None:
            raise ValueError("RESUME_REQUIRES_ORIGINAL_PDF")
        prepared = prepare_tool_state(restored_checkpoint, resume_pdf_bytes)
        financial_submission = prepared["financial_submission"]
        observed_tool_calls = prepared["observed_tool_calls"]
        submission_attempts = prepared["submission_attempts"]
        review_state = prepared["review_state"]

    else:
        financial_submission = {}
        observed_tool_calls = []
        submission_attempts = {"count": 0}
        review_state = {
            "reviewed_count": 0, "status": None,
            "page_reads": 0, "reads_at_review": 0,
        }

    @function_tool(needs_approval=financial_approval_required)
    def submit_financial_data(
        company: str,
        fiscal_year: int,
        currency: str,
        units: str,
        revenue_current: float,
        revenue_previous: float,
        gross_profit: float,
        net_income: float,
        reported_revenue_growth: float,
        reported_gross_margin: float,
        reported_net_margin: float,
        source_page: int,
        revenue_current_page: int,
        revenue_previous_page: int,
        gross_profit_page: int,

        net_income_page: int,
        operating_income: float | None = None,
        operating_income_page: int | None = None,
        operating_cash_flow: float | None = None,
        operating_cash_flow_page: int | None = None,
        capital_expenditure: float | None = None,
        capital_expenditure_page: int | None = None,
        subscription_revenue: float | None = None,
        subscription_revenue_page: int | None = None,

        operating_cash_flow_previous: float | None = None,
        operating_cash_flow_previous_page: int | None = None,
        operating_cash_flow_two_years_ago: float | None = None,
        operating_cash_flow_two_years_ago_page: int | None = None,
        capital_expenditure_previous: float | None = None,
        capital_expenditure_previous_page: int | None = None,
        capital_expenditure_two_years_ago: float | None = None,
        capital_expenditure_two_years_ago_page: int | None = None,
        share_repurchases: float | None = None,
        share_repurchases_page: int | None = None,
        stock_based_compensation: float | None = None,
        stock_based_compensation_page: int | None = None,
        deferred_revenue_change: float | None = None,
        deferred_revenue_change_page: int | None = None,


    ) -> str:

        """Submit financial figures extracted from the
        PDF, together with the reported or calculated
        percentages and the financial statement page.
        Only call when all fields have been located.
        All monetary values must use matching units.
        """


        page_references = {
            "source_page": source_page,
            "revenue_current_page": revenue_current_page,
            "revenue_previous_page": revenue_previous_page,
            "gross_profit_page": gross_profit_page,
            "net_income_page": net_income_page,
        }

        for name, page_number in page_references.items():
            if not 1 <= page_number <= len(pages):
                return (
                    f"Invalid PDF page for {name}: "
                    f"{page_number}. The PDF contains "
                    f"{len(pages)} pages."
                )

        optional_metrics = {
            "operating_income": (
                operating_income, operating_income_page
            ),
            "operating_cash_flow": (
                operating_cash_flow, operating_cash_flow_page
            ),
            "capital_expenditure": (
                capital_expenditure, capital_expenditure_page
            ),
            "subscription_revenue": (
                subscription_revenue, subscription_revenue_page
            ),

            "operating_cash_flow_previous": (
                operating_cash_flow_previous,
                operating_cash_flow_previous_page,
            ),
            "operating_cash_flow_two_years_ago": (
                operating_cash_flow_two_years_ago,
                operating_cash_flow_two_years_ago_page,
            ),
            "capital_expenditure_previous": (
                capital_expenditure_previous,
                capital_expenditure_previous_page,
            ),
            "capital_expenditure_two_years_ago": (
                capital_expenditure_two_years_ago,
                capital_expenditure_two_years_ago_page,
            ),
            "share_repurchases": (
                share_repurchases,
                share_repurchases_page,
            ),
            "stock_based_compensation": (
                stock_based_compensation,
                stock_based_compensation_page,
            ),
            "deferred_revenue_change": (
                deferred_revenue_change,
                deferred_revenue_change_page,
            ),

        }

        for metric, (value, page) in optional_metrics.items():
            if value is None and page is None:
                continue

            if value is None or page is None:
                return (
                    f"{metric} requires both a value and "
                    "a supporting PDF page, or neither."
                )

            if not isinstance(page, int) or not 1 <= page <= len(pages):
                return f"Invalid PDF page for {metric}: {page}"


        refusal = submission_block_reason(
            submission_attempts["count"],
            review_state["reviewed_count"],
            review_state["status"],
            review_state["page_reads"] - review_state["reads_at_review"],
        )
        if refusal:
            return refusal

        previous_submission = financial_submission.copy()
        financial_submission.clear()
        financial_submission.update({
            "company": company,
            "fiscal_year": fiscal_year,
            "currency": currency,
            "units": units,
            "revenue_current": revenue_current,
            "revenue_previous": revenue_previous,
            "gross_profit": gross_profit,
            "net_income": net_income,

            "operating_income": operating_income,
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditure": capital_expenditure,
            "subscription_revenue": subscription_revenue,

            "operating_cash_flow_previous": operating_cash_flow_previous,
            "operating_cash_flow_two_years_ago": operating_cash_flow_two_years_ago,
            "capital_expenditure_previous": capital_expenditure_previous,
            "capital_expenditure_two_years_ago": capital_expenditure_two_years_ago,
            "share_repurchases": share_repurchases,
            "stock_based_compensation": stock_based_compensation,
            "deferred_revenue_change": deferred_revenue_change,

            "reported": {
                "revenue_growth": reported_revenue_growth,
                "gross_margin": reported_gross_margin,
                "net_margin": reported_net_margin,
            },
            "source_page": source_page,

            "source_pages": {
                "revenue_current": revenue_current_page,
                "revenue_previous": revenue_previous_page,
                "gross_profit": gross_profit_page,
                "net_income": net_income_page,
                "operating_income": operating_income_page,
                "operating_cash_flow": operating_cash_flow_page,
                "capital_expenditure": capital_expenditure_page,
                "subscription_revenue": subscription_revenue_page,

                "operating_cash_flow_previous": operating_cash_flow_previous_page,
                "operating_cash_flow_two_years_ago": operating_cash_flow_two_years_ago_page,
                "capital_expenditure_previous": capital_expenditure_previous_page,
                "capital_expenditure_two_years_ago": capital_expenditure_two_years_ago_page,
                "share_repurchases": share_repurchases_page,
                "stock_based_compensation": stock_based_compensation_page,
                "deferred_revenue_change": deferred_revenue_change_page,

            },


        })

        optional_issues = validate_optional_financial_data(
            financial_submission,
            total_pages=len(pages),
        )

        if optional_issues:
            financial_submission.clear()
            financial_submission.update(previous_submission)
            return (
                "Financial submission rejected: "
                + "; ".join(optional_issues)
            )

        if previous_submission and not financial_correction_changes(
            previous_submission, financial_submission
        ):
            financial_submission.clear()
            financial_submission.update(previous_submission)
            return (
                "NO_CORRECTION_MADE: The revised submission does not "
                "change financial figures, periods, source pages, or units. "
                "Preserve the original review and report unresolved issues."
            )

        updated, injected = inject_first_submission_error(
            financial_submission, pages, enabled=inject_test_error,
            accepted_count=submission_attempts["count"],
        )
        if injected:
            financial_submission.clear()
            financial_submission.update(updated)
            print("SYNTHETIC TEST: intentionally injected wrong FY2025 revenue.")
        submission_attempts["count"] += 1
        observed_tool_calls.append("submit_financial_data")
        review_state["status"] = None

        return (
            "Financial data received for validation. "
            f"Successful submission {submission_attempts['count']} of 2. "
            "Call review_submitted_financials before finalising."
        )

    @function_tool
    def search_report(query: str) -> str:
        """Search all pages of the uploaded PDF for
        information. Returns page-labelled excerpts.
        """
        matches = find_evidence(pages, query)

        if not matches:
            return "No matching evidence found."

        return "\n\n---\n\n".join(
            f"PDF page {number}\n{excerpt}"
            for _, number, excerpt in matches
        )

    @function_tool
    def read_page(page_number: int) -> str:
        """Read a full PDF page by its 1-based page number.
        Use to verify evidence and financial figures.
        """
        if not 1 <= page_number <= len(pages):
            return "Invalid page number."

        observed_tool_calls.append("read_page")
        review_state["page_reads"] += 1
        return (
            f"PDF page {page_number}\n"
            + pages[page_number - 1][:12000]
        )

    @function_tool
    def calculate_percentage(
        numerator: float,
        denominator: float
    ) -> str:
        """Calculate numerator / denominator * 100.
        Use for margins and other financial ratios.
        Both values must have matching units.
        """
        if denominator == 0:
            return "Error: denominator is zero."

        value = numerator / denominator * 100
        return f"{value:.2f}%"

    @function_tool
    def calculate_growth(
        current: float,
        previous: float
    ) -> str:
        """Calculate period-over-period percentage growth.
        Values must use matching units and periods.
        """
        if previous == 0:
            return "Error: previous value is zero."

        growth = (current - previous) / abs(previous) * 100
        return f"{growth:.2f}%"



    @function_tool
    def review_submitted_financials() -> str:
        """Review submitted figures and return validation feedback."""
        import json

        result = review_financial_evidence(
            pages,
            financial_submission,
        )
        observed_tool_calls.append("review_submitted_financials")
        review_state["reviewed_count"] = submission_attempts["count"]
        review_state["status"] = result["status"]
        review_state["reads_at_review"] = review_state["page_reads"]
        result["next_actions"] = investigation_next_actions(result)

        return json.dumps(result, default=str)

    agent = Agent(
        name="AI Due Diligence Analyst",
        model=offline_scripted_model if resume_mode == "OFFLINE_SDK_RESUME" else "gpt-5-mini",
        tools=[
            search_report,
            read_page,
            calculate_percentage,
            calculate_growth,
            submit_financial_data,
            review_submitted_financials,
        ],
        instructions="""


You are a senior financial and technology due diligence analyst
preparing a preliminary report for an investment or consulting team.

Your role is to translate information from the uploaded company
report into commercially relevant findings, supported by evidence.

Use the available tools to examine the document before drawing
conclusions.


RESEARCH PROCESS — PRIVATE EQUITY AND M&A DUE DILIGENCE

1. Establish the company, fiscal period, reporting currency,
units, business model and major operating segments.

2. Read the primary financial statements and relevant notes.
Extract the financial inputs available for structured validation.
Record supporting 1-based PDF page positions.

3. Analyse financial performance across available periods.
Investigate revenue growth, gross and operating profitability,
cost movements, operating cash flow, capital expenditure and
material non-recurring items where disclosed. Reconcile units
and reporting periods before comparing figures.

4. Evaluate earnings quality without inventing adjusted EBITDA.
Identify disclosed exceptional items, acquisition-related
charges and accounting factors affecting comparability.
Distinguish reported earnings from normalised earnings that
would require management information or further analysis.

5. Evaluate revenue quality and business-model economics.
Investigate recurring revenue, customer concentration,
retention, pricing, organic versus acquired growth and
contractual visibility where evidence is available. Distinguish
disclosed evidence from information that requires management
validation.

6. Evaluate technology and operational diligence exposures.
Review disclosed architecture and hosting dependencies,
cybersecurity, resilience, software and third-party risks,
AI-related economics and potential technical investment needs.
Do not claim to have tested systems or controls.

7. Identify potential value-creation opportunities and risks.
Connect each material issue to a plausible effect on future
revenue, margins, cash flow, capital requirements, integration
complexity or investment-case execution. Do not assign
unsupported valuations, probabilities or financial forecasts.

8. Challenge the preliminary investment thesis. For each
material conclusion, consider alternative explanations,
missing evidence and whether the finding is relevant enough
to influence a diligence decision.

9. Prioritise management information requests by the
potential for their answers to change the preliminary
assessment. Where possible, identify the specific financial,
commercial or technology assumption being tested.

10. Produce the six required report sections. Support material
claims with pages actually reviewed and distinguish reported
facts, calculated metrics, reasonable hypotheses and
unresolved evidence gaps.


COMMERCIAL AND TECHNOLOGY INVESTMENT-THESIS TEST

For each material commercial or technology issue, reason
through four questions before including it in the report:

1. What does the filing actually establish?
   Identify the specific disclosure, trend or financial
   figure and its supporting PDF page.

2. Which investment-case assumption could it affect?
   Consider revenue growth, customer retention, pricing,
   operating margins, cash flow, required investment,
   business continuity or execution complexity.

3. What alternative explanation or uncertainty matters?
   Distinguish evidence from hypotheses. A risk disclosed
   in a filing is not proof that the risk has materialised.
   A product capability is not proof of competitive advantage.

4. What evidence would change the assessment?
   Identify the specific management data, contract,
   operating metric, technical review or independent test
   needed to resolve the question.

COMMERCIAL DILIGENCE PRIORITIES

Investigate available evidence on segment growth,
revenue composition, organic versus acquired growth,
pricing and volumes, ARR or contracted revenue,
customer retention, concentration, competition,
distribution dependencies and recurring-revenue quality.

Assess whether observed growth could reasonably be
extrapolated, and identify what would challenge that
assumption. Do not treat subscription mix, ARR growth,
product integration or management claims as proof of
retention, pricing power or competitive defensibility.

TECHNOLOGY DILIGENCE PRIORITIES

Investigate available evidence on software architecture,
cloud and hosting dependencies, scalability, technical
debt, cybersecurity, resilience, privacy, data/IP rights,
AI training and inference costs, integration requirements
and technology-related investment needs.

Distinguish disclosed technology capabilities from
independently validated operational performance.
Do not infer system reliability, secure architecture,
low technical debt or efficient AI economics solely
from a company's product descriptions.

PRIORITISATION

Focus the detailed analysis on the issues most capable
of changing an investment thesis. Explain the
commercial or financial transmission mechanism,
but do not invent financial estimates or risk ratings.

Where the filing lacks material evidence, identify
the gap and the next diligence action rather than
manufacturing an assessment.

Avoid repeating a finding across the financial,
technology and risk sections unless it contributes
a materially different investment implication.


REPORTING STANDARD — FINANCIAL AND TECHNOLOGY DUE DILIGENCE

Prepare a preliminary, decision-oriented assessment for a consulting or investment team. Analyse what the uploaded filing establishes, why it matters commercially, what remains uncertain, and what should be investigated next. Do not merely summarise the annual report.

ANALYTICAL DISCIPLINE

- Support each material factual claim with evidence from pages you have read. Cite 1-based PDF page positions for material figures and claims.
- Clearly distinguish reported facts, derived calculations, analyst interpretation, and unresolved questions through natural wording. Never invent data or citations.
- Compare reporting periods when evidence permits. Separate underlying trends from one-off items and check consistency of fiscal periods and units.
- Do not infer customer retention from subscription mix; operating leverage from gross margin alone; free cash flow from operating cash flow; or control effectiveness from disclosed policies.
- Do not infer competitive advantage from product integration, or quantify AI monetisation and unit economics without supporting data.
- If two sources or figures conflict, investigate and reconcile them. If you cannot resolve the inconsistency, state the uncertainty; do not quietly select one.
- Describe opportunities and risks proportionately. Avoid claims of proven durability, defensibility or materiality unless the evidence supports them.
- Do not assign arbitrary risk ratings, valuations, forecasts or buy/sell recommendations.

WRITING STANDARD


- Within the Financial and commercial assessment, use
  two or three conclusion-led level-two headings to
  examine commercial drivers not already covered by
  the structured financial insights. Focus on revenue
  drivers, business-model economics and competitive
  positioning where the filing provides evidence.

- Within the Technology and operational assessment,
  use two or three conclusion-led level-two headings
  covering the most material technology exposures.
  Explain the disclosed evidence, its investment
  relevance and the specific remaining uncertainty
  in connected analytical paragraphs.

- Avoid short standalone labels such as
  "Revenue and segmentation", "Profitability and costs",
  "Operational dependencies and risk disclosures",
  or "Implication and further testing required".
  Replace them with headings that communicate a finding.

- Do not place a bullet beneath every subheading.
  Use analytical paragraphs for commercial and
  technology assessments. Reserve numbered lists for
  priority risks and management information requests.

- Treat the structured financial insights as already
  presented. The narrative should add distinct
  commercial and technology analysis rather than
  repeat the same financial figures and diligence actions.

- Lead with a conclusion supported by evidence and explain the commercial consequence. Address a meaningful alternative explanation or uncertainty when relevant.
- Use natural, connected analytical paragraphs for the main assessment sections, usually one argument per paragraph. Avoid turning the document into an extended list of facts.
- Use specific, conclusion-led subheadings where helpful. Keep each section focused on a distinct decision-relevant question.
- Use bullets or numbering only for the three executive findings, priority diligence issues and management requests.
- Do not print mechanical labels such as "Finding", "Evidence", "Facts", "Calculations", "Commercial implication", "Inferences", "Further diligence" or "Three headline points" as repeated headings or prefixes.
- Avoid filler, exaggerated adjectives, internal instructions, technical tool commentary, chatbot closings and unresolved placeholders.
- Do not repeat the same numerical facts, uncertainties or recommendations across sections unless they serve genuinely different arguments.
- Prefer precise language over phrases such as "clear growth engine", "mature security", "high-quality cash flows" or "defensible moat" when evidence is limited.

REQUIRED REPORT STRUCTURE

Use exactly these six top-level Markdown headings (with a single #). You may add concise, conclusion-led level-two headings (##) within sections.

# Executive assessment

Begin with one short, coherent paragraph stating the preliminary assessment, financial strengths and the two or three uncertainties most capable of changing it. Then provide exactly three numbered findings. Each numbered item must have a brief, conclusion-led title and a short supporting paragraph immediately beneath it. Do not write the word "Finding" before the title, and do not label the paragraph "Evidence". The three findings should synthesise different issues rather than repeat financial figures. Keep detail for later sections.

# Financial and commercial assessment

Explain revenue growth, profitability, cash generation and revenue composition with year-on-year comparisons where available. Assess drivers and commercial implications; distinguish what the numbers show from what requires retention, customer or unit-economics evidence. Do not equate cash from operations with free cash flow or high gross margin with proven operating leverage.


COMMERCIAL ASSESSMENT — DISTINCT ANALYTICAL FINDINGS

The structured financial diligence component already presents
revenue growth, profitability, free cash flow and capital-allocation
metrics. Do not repeat these as separate narrative summaries.

Use two or three conclusion-led level-two headings to investigate
the most material commercial questions for this specific company.

Prioritise:
- The drivers of growth: price, volume, customer acquisition,
  expansion, usage, acquisitions and segment mix where disclosed.
- Revenue quality: renewals, customer concentration, contracts,
  pricing resilience and recurring versus transactional demand.
- Competitive economics: product differentiation, substitution
  threats, distribution advantages and cost-to-serve where evidenced.

For each commercial finding:
1. State the conclusion, qualified to the strength of the evidence.
2. Present the most relevant company-specific evidence and PDF pages.
3. Explain which investment-case assumption the evidence could affect.
4. Identify the important alternative explanation or missing information.
5. Specify the data that would help resolve the uncertainty.

Write connected analytical paragraphs rather than bullet summaries.
Use financial figures selectively when they directly support a
new commercial conclusion.

Avoid generic headings such as "Growth, margins and revenue
composition", "Cash generation and capital allocation" and
"Profitability quality caveats" in the commercial narrative.

If the source does not establish an issue, say what remains
unverified rather than presenting a hypothesis as a finding.

Do not invent customer retention, pricing power, market shares,
organic growth splits, cloud unit economics or competitive moats.


# Technology and operational assessment

Assess disclosed product innovation, AI initiatives, dependencies, cybersecurity, resilience and governance in terms of possible impacts on growth, margins, customer trust and execution. Public disclosures about controls are not proof that those controls work. State which assessments require architecture reviews, technical testing or independent evidence.

# Growth opportunities and key risks

Prioritise three to five commercially relevant opportunities or risks. Explain for each why it could affect performance, which facts support the assessment, what is uncertain and what evidence would resolve it. Avoid re-listing the financial results or duplicating the executive findings.

# Priority diligence workplan

Provide exactly five concrete management questions or document requests, ordered by how much the answers could affect the preliminary assessment. Make each request specific and actionable. Do not include placeholders such as ">X%" or "TBD".

# Evidence and limitations

Provide a concise list or paragraph identifying the most important supporting PDF pages and significant evidence gaps. State that this is a preliminary filing-based assessment and that relevant conclusions require human review and, where appropriate, management or third-party verification. Do not append a second conclusion, separate facts/calculations/inferences inventories, or conversational sign-off.

FINAL REVIEW BEFORE RESPONDING

Check that the six required headings appear exactly once and in order; the executive findings are three numbered titles with paragraph support; the body is primarily prose; every material conclusion is appropriately evidenced or qualified; numerical claims are reconciled; and no sections or labels repeat unnecessarily. Never present arithmetic agreement as independent source verification.


FINANCIAL VERIFICATION WORKFLOW

After locating and reading the supporting financial
statement pages, submit the structured financial data
using submit_financial_data.

Then call review_submitted_financials before producing
the final due diligence report.


INVESTIGATION DECISION RULES

The financial review tool returns an overall status,
arithmetic checks, source checks, statement checks,
and financial metadata issues.

If the overall status is PRELIMINARY_CHECKS_PASSED:
- Continue the due diligence assessment.
- Do not treat this status as independent proof
  of accounting accuracy or earnings quality.

If the overall status is NEEDS_REVIEW:
- Identify the specific failed or uncertain checks.
- Determine whether the issue is a calculation error,
  wrong financial statement row, incorrect fiscal year,
  unsupported source, or missing financial metadata.
- Use search_report or read_page to investigate
  evidence that could resolve the issue.
- Correct submitted financial data only when supported
  by the original document.
- You may resubmit financial data once and run the
  financial review again.
- If evidence remains unavailable or ambiguous,
  preserve the original uncertainty and explain it
  in the final report.

Never invent missing information or change a value
merely to make validation pass.

Do not repeatedly investigate the same unresolved
issue. Prioritise material discrepancies and finish
with a clear statement of remaining limitations.


Inspect all arithmetic failures and source warnings.

If a discrepancy is found, use read_page to revisit
the relevant financial statement and investigate it.

If you find reliable evidence supporting a correction,
you may resubmit financial data once and run the review
again.

Never change figures simply to make a test pass.

If the discrepancy cannot be resolved, clearly identify
the affected figure as unverified in the final report.

Arithmetic agreement is not proof of source accuracy.
Finding a number on a PDF page does not prove the
correct metric, fiscal year or monetary units.


OPTIONAL FINANCIAL EXTRACTION


HISTORICAL CASH FLOW AND CAPITAL ALLOCATION

When the filing clearly provides comparable cash flow
statements, also extract these optional figures:

- Previous-year operating cash flow and supporting PDF page.
- Operating cash flow two years ago and supporting PDF page.
- Previous-year capital expenditure and supporting PDF page.
- Capital expenditure two years ago and supporting PDF page.
- Current-year share repurchases and supporting PDF page.
- Current-year stock-based compensation and supporting PDF page.
- Current-year change in deferred revenue and supporting PDF page.

Use the same reporting currency and monetary units for
all years. Confirm the fiscal-year column headings.

Express capital expenditure and share repurchases as
positive cash amounts spent, even if the statements
show these cash outflows in parentheses.

Preserve the signed value of the deferred revenue
movement because it can be positive or negative.

Stock-based compensation is a non-cash adjustment.
Do not assume it has no economic cost.

Do not claim that operating cash flow funded all share
repurchases unless the complete financing and cash
movements support that interpretation.

For every supplied optional value, provide its actual
1-based PDF page position.

If any figure is unavailable or ambiguous, submit null
for both its value and its supporting page.

Prioritise accurate core financial extraction over
completing every optional metric.


When clearly available in the uploaded filing, also extract:

- Operating income and its 1-based PDF page.
- Net cash provided by operating activities and its PDF page.
- Capital expenditure or purchases of property and equipment
  and the supporting PDF page.
- Subscription revenue and its supporting PDF page.

These optional metrics must use the same fiscal period,
currency and monetary units as the core financial data.

For capital expenditure, provide the positive amount of
cash spent on capital assets, excluding acquisitions.
Do not equate depreciation with capital expenditure.

Subscription revenue applies only where separately disclosed.

If an optional figure is unavailable or ambiguous, submit
null for both its value and source page. Never estimate it,
copy it from another reporting period, or use a figure merely
because it appears in the narrative.

Do not delay or omit the core financial submission because
an optional metric cannot be established.


Submit monetary values in consistent units.
Use the calculator tools for the three percentages.

For submit_financial_data, provide a separate PDF page
number for each financial figure:

- revenue_current_page: current-year revenue
- revenue_previous_page: prior-year revenue
- gross_profit_page: gross profit
- net_income_page: net income

Use the 1-based PDF page positions returned by the
read_page tool, not printed page numbers in the filing.

Read each supporting page before submitting figures.
Only submit figures whose values and source pages
you can identify from the uploaded PDF.

Keep source_page as the primary financial statement
page for backwards compatibility.

Do not invent page numbers or financial values.


If any required input is unavailable, do not guess
or fabricate values merely to submit the data.
"""
    )

    interrupted = False
    try:
        result = Runner.run_sync(
            agent,
            sdk_resume_state if resume_mode == "OFFLINE_SDK_RESUME" else (
    "Prepare a comprehensive, evidence-led "
    "preliminary Private Equity and M&A "
    "due diligence assessment of the uploaded "
    "company report. Investigate the financial "
    "statements and relevant notes, business "
    "model, revenue quality, cash generation, "
    "technology exposures and growth drivers. "
    "Prioritise findings that could affect an "
    "investment thesis, future earnings, cash "
    "flow, capital requirements or execution "
    "risk. For material findings, explain the "
    "evidence, commercial implication, "
    "uncertainty and next diligence action. "
    "Use the required six-section report "
    "structure. Do not manufacture conclusions "
    "when evidence is unavailable. Use the "
    "search, page-reading and calculator tools."
),

        max_turns=permitted_turn_limit(max_turns),
        )
    except Exception as error:
        from agents.exceptions import MaxTurnsExceeded
        if not isinstance(error, MaxTurnsExceeded):
            raise
        from types import SimpleNamespace
        interrupted = True
        resume_inspection = inspect_replay_boundary(extract_resume_input(error))
        print("Resume transcript inspection:", resume_inspection["reason"])
        print("Max turns is not a supported paused RunState; preserving tool progress only.")
        result = SimpleNamespace(
            new_items=[],
            final_output=interrupted_report(
                financial_submission, review_state["reviewed_count"],
                submission_attempts["count"], review_state["status"],
            ),
        )



    # Approval-pause snapshots remain in memory and are not persisted.
    sdk_pause_capture = capture_approval_pause(result) if not interrupted else None
    if sdk_pause_capture is not None and sdk_pause_capture["paused"]:
        # An approval pause is not a completed financial investigation.
        # Do not export it as a finished report or cache its partial output.
        # Full approval/resume UI remains intentionally disabled.
        if pause_pdf_bytes is None:
            raise RuntimeError(
                "SDK_APPROVAL_PAUSED: original PDF bytes required to capture "
                "a document-bound financial checkpoint; live resume disabled."
            )
        handoff = make_financial_pause_handoff(
            sdk_pause_capture, pause_pdf_bytes, financial_submission,
            submission_attempts["count"], review_state["reviewed_count"],
            review_state["status"], observed_tool_calls,
            review_state["page_reads"], review_state["reads_at_review"],
        )
        raise SDKFinancialApprovalPaused(handoff)

    # Record the agent's tool calls without logging
    # document contents or tool arguments.
    tool_calls = []

    for item in result.new_items:
        if item.type == "tool_call_item":
            raw_item = item.raw_item

            tool_name = getattr(raw_item, "name", None)

            if not tool_name:
                function = getattr(raw_item, "function", None)
                tool_name = getattr(function, "name", None)

            if not tool_name:
                tool_name = "unknown_tool"

            tool_calls.append(str(tool_name))

    if not tool_calls:
        tool_calls = observed_tool_calls.copy()

    print("\nAI INVESTIGATION AUDIT")
    print("Tool calls:", len(tool_calls))

    for index, tool_name in enumerate(tool_calls, 1):
        print(f"{index}. {tool_name}")

    required_tools = [
        "submit_financial_data",
        "review_submitted_financials",
    ]

    for tool_name in required_tools:
        status = "CALLED" if tool_name in tool_calls else "NOT CALLED"
        print(f"{tool_name}: {status}")

    audit = investigation_outcome(
        submission_attempts["count"],
        review_state["reviewed_count"],
        review_state["status"],
        tool_calls,
    )
    sequence_audit = assess_tool_sequence(tool_calls)
    print("Tool sequence valid:", sequence_audit["sequence_ok"])
    if sequence_audit["issues"]:
        print("Sequence issues:", ", ".join(sequence_audit["issues"]))
    print("Investigation outcome:", audit["outcome"])
    evaluation = evaluate_agent_run(
        pages, financial_submission, tool_calls,
        submission_attempts["count"], review_state["reviewed_count"],
        review_state["status"],
    )
    if sdk_pause_capture is not None and sdk_pause_capture["paused"]:
        evaluation["evaluation"] = "SDK_PAUSED_APPROVAL_PENDING"
        evaluation["sdk_pause"] = pause_public_status(sdk_pause_capture)
        evaluation["issues"] = list(dict.fromkeys(
            evaluation["issues"] + ["APPROVAL_PENDING_RESUME_DISABLED"]
        ))
    if interrupted:
        evaluation["evaluation"] = "INTERRUPTED_TURN_LIMIT"
        evaluation["resume_inspection"] = resume_inspection
        evaluation["sdk_resume_policy"] = classify_run_boundary(max_turns_error=True)
        evaluation["issues"] = list(dict.fromkeys(
            evaluation["issues"] + ["AGENT_MAX_TURNS_EXCEEDED"]
        ))
    print("Agent evaluation:", evaluation["evaluation"])
    if evaluation["issues"]:
        print("Evaluation issues:", ", ".join(evaluation["issues"]))
    print("Latest submission reviewed:", audit["latest_submission_reviewed"])

    
    report = str(result.final_output)
    final_review = trusted_latest_review(
        pages, financial_submission, submission_attempts["count"], review_state
    )
    report = finalise_dd_report(report, financial_submission, final_review)
    report = append_audit_appendix(report, audit, sequence_audit)
    narrative_issues = find_reversed_revenue_arrows(report, financial_submission)
    if narrative_issues:
        print("Narrative chronology warning:", "; ".join(narrative_issues))
        report += ("\n\n### Automated chronology warning\n\n"
                   + "\n\n".join(narrative_issues)
                   + "\n\nReview the narrative against the cited financial statements.")

    validation_results = None

    if financial_submission:
        submitted = financial_submission

        data = FinancialData(
            company=submitted["company"],
            fiscal_year=submitted["fiscal_year"],
            currency=submitted["currency"],
            units=submitted["units"],
            revenue_current=submitted["revenue_current"],
            revenue_previous=submitted["revenue_previous"],
            gross_profit=submitted["gross_profit"],
            net_income=submitted["net_income"],
        )

        validation_results = validate_financials(
            data,
            submitted["reported"],
        )

    return report, validation_results, financial_submission.copy(), evaluation



# -----------------------------
# Streamlit dashboard
# -----------------------------

st.subheader("1. Upload company report")

uploaded_file = st.file_uploader(
    "Select a PDF annual report",
    type=["pdf"],
)

if uploaded_file is not None:

    pdf_bytes = uploaded_file.getvalue()

    # Clear the previous report if the file changes
    file_id = (
        uploaded_file.name,
        len(pdf_bytes),
        __import__("hashlib").sha256(
            pdf_bytes
        ).hexdigest()
    )


    if st.session_state.get("file_id") != file_id:
        st.session_state["file_id"] = file_id
        st.session_state.pop("report", None)
        st.session_state.pop("validation", None)
        st.session_state.pop("financial_data", None)
        st.session_state.pop("agent_evaluation", None)
        st.session_state.pop("offline_approval_queue", None)
        st.session_state.pop("sdk_offline_approval", None)
        st.session_state.pop("financial_resume_demo", None)
        st.session_state.pop("financial_resume_result", None)
        st.session_state.pop("live_financial_pause", None)
        st.session_state.pop("live_continuation_preflight", None)

    # Reload previously saved analysis
    if "report" not in st.session_state:
        saved = load_report(pdf_bytes)

        if saved:
            st.session_state["report"] = saved["report"]
            st.session_state["validation"] = saved.get("validation")
            st.session_state["financial_data"] = saved.get(
                "financial_data"
            )
            st.success(
                "Previously saved analysis loaded. "
                "No OpenAI API call needed."
            )



    if len(pdf_bytes) > 15 * 1024 * 1024:
        st.error("Please upload a PDF smaller than 15 MB.")
        st.stop()

    try:
        pages = extract_pages(pdf_bytes)
    except Exception as error:
        st.error(f"Could not read PDF: {error}")
        st.stop()

    readable = sum(bool(page.strip()) for page in pages)

    col1, col2, col3 = st.columns(3)

    col1.metric("Total pages", len(pages))
    col2.metric("Readable pages", readable)
    col3.metric(
        "File size",
        f"{len(pdf_bytes) / 1024 / 1024:.2f} MB"
    )

    if readable == 0:
        st.error(
            "No readable text found. "
            "Scanned PDFs will need OCR support."
        )
        st.stop()

    st.subheader("2. Check source evidence")

    evidence = find_evidence(
        pages,
        "total revenue net income",
        limit=3,
    )

    with st.expander("Preview financial evidence"):
        if evidence:
            for _, number, excerpt in evidence:
                st.markdown(f"**PDF page {number}**")
                st.text(excerpt[:1100])
        else:
            st.info(
                "No matching financial excerpt found."
            )

    st.caption(
        "These are search results, not yet verified "
        "financial figures. The agent will examine "
        "supporting pages."
    )

    st.subheader("3. Run AI analysis")

    st.checkbox(
        "Controlled smoke test (8 agent turns; still uses paid API credits)",
        key="smoke_test_mode",
        help=(
            "Limits the agent's turns for a short evaluation. "
            "This is not a monetary spending cap or a guarantee "
            "that the diligence report will be complete."
        ),
    )

    st.checkbox(
        "Inject wrong first revenue submission (synthetic conflict PDF only)",
        key="inject_test_error",
        help=(
            "Only works on synthetic_conflict_test.pdf. "
            "The first accepted FY2025 revenue of 120 is changed to 130 "
            "to test whether the agent finds and fixes the error. "
            "Uses paid API credits when analysis runs."
        ),
    )

    st.checkbox(
        "Pause paid investigation for financial submission approval (experimental)",
        key="real_financial_approval_mode",
        help=(
            "Requires a paid AI analysis run. Captures genuine SDK approval and "
            "financial checkpoint in this session; real paid resumption is disabled."
        ),
    )

    live_handoff = st.session_state.get("live_financial_pause")
    if live_handoff is not None:
        from live_financial_pause_handoff import public_financial_pause_status
        public_pause = public_financial_pause_status(live_handoff)
        st.warning(
            "Real investigation paused for financial approval. "
            "No completed report was produced. Paid resume is disabled."
        )
        st.write("Pending approval checkpoint:", public_pause)
        if live_handoff.get("status") == "AWAITING_APPROVAL":
            st.caption(
                "This decision will be applied to the paused SDK state. "
                "It will not resume the AI model or use additional API credits."
            )
            approve_live, reject_live = st.columns(2)
            if approve_live.button("Approve paused financial submission"):
                try:
                    decide_live_financial_pause(live_handoff, pdf_bytes, True)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
            if reject_live.button("Reject paused financial submission"):
                try:
                    decide_live_financial_pause(live_handoff, pdf_bytes, False)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info(
                "Financial submission decision recorded: "
                f"{live_handoff['status']}. The model has not resumed."
            )
            if live_handoff["status"] == "APPROVED":
                if st.button("Check financial continuation readiness (FREE)"):
                    try:
                        st.session_state["live_continuation_preflight"] = (
                            preflight_live_continuation(live_handoff, pdf_bytes)
                        )
                    except ValueError as error:
                        st.error(str(error))
                ready = st.session_state.get("live_continuation_preflight")
                if ready is not None:
                    st.write("Continuation checks:", ready)
                    st.caption("No AI model resumed; paid continuation remains disabled.")
        if st.button("Discard paused investigation"):
            st.session_state.pop("live_financial_pause", None)
            st.rerun()

    st.subheader("FREE approval interface demo")
    st.caption(
        "Synthetic decision queue only. No AI, no API credits, "
        "and no resumed investigation."
    )
    if st.button("Start FREE approval demo"):
        st.session_state["offline_approval_queue"] = start_offline_approval(pdf_bytes)
    demo_queue = st.session_state.get("offline_approval_queue")
    if demo_queue is not None:
        from approval_queue import approval_public_status
        public_approval = approval_public_status(demo_queue)
        st.write("Approval status:", public_approval["approvals"][0])
        if public_approval["approvals"][0] == "PENDING":
            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve demo submission"):
                finish_offline_approval(demo_queue, pdf_bytes, True)
                st.success("Synthetic approval recorded. No tool or model was run.")
            if reject_col.button("Reject demo submission"):
                finish_offline_approval(demo_queue, pdf_bytes, False)
                st.info("Synthetic rejection recorded. No tool or model was run.")

    st.subheader("FREE real-SDK approval demo")
    st.caption(
        "A scripted local model creates a real SDK pause. "
        "Approval/rejection is applied to RunState, but the model is NOT resumed."
    )
    if st.button("Create FREE SDK approval pause"):
        st.session_state["sdk_offline_approval"] = start_sdk_offline_approval(pdf_bytes)
        st.success("SDK RunState paused. No external model calls.")
    sdk_demo = st.session_state.get("sdk_offline_approval")
    if sdk_demo is not None:
        from approval_queue import approval_public_status
        sdk_public = approval_public_status(sdk_demo)
        if sdk_demo.get("decisions_applied") and not sdk_demo.get("offline_resumed"):
            if st.button("Resume FREE scripted SDK demo"):
                result = resume_sdk_offline_approval(sdk_demo, pdf_bytes)
                st.success(
                    "Real SDK continuation completed using a scripted offline model. "
                    f"Executed synthetic submissions: {len(result['executed_submissions'])}. "
                    "No external API calls."
                )
                st.rerun()
        elif sdk_demo.get("offline_resumed"):
            st.success(
                "FREE scripted SDK resume completed. "
                f"Synthetic submissions executed: {len(sdk_demo['_offline_executed'])}. "
                "External API calls: 0."
            )
        if sdk_public["approvals"][0] == "PENDING":
            sdk_yes, sdk_no = st.columns(2)
            if sdk_yes.button("Approve SDK demo"):
                decide_sdk_offline_approval(sdk_demo, pdf_bytes, True)
                st.rerun()
            if sdk_no.button("Reject SDK demo"):
                decide_sdk_offline_approval(sdk_demo, pdf_bytes, False)
                st.rerun()
        elif sdk_public["approvals"][0] == "APPROVED":
            st.success("SDK financial submission approval: APPROVED. No model resumed or API call made.")
        elif sdk_public["approvals"][0] == "REJECTED":
            st.info("SDK financial submission approval: REJECTED. No financial tool executed.")

    st.subheader("FREE complete financial correction demo")
    st.caption("Actual SDK with scripted offline model. No external API calls.")
    if st.button("Start FREE financial resume test"):
        try:
            st.session_state["financial_resume_demo"] = start_financial_resume_demo(pdf_bytes)
            st.session_state.pop("financial_resume_result", None)
        except ValueError as error:
            st.error(str(error))
    test_session = st.session_state.get("financial_resume_demo")
    if test_session is not None:
        test_result = st.session_state.get("financial_resume_result")
        if test_result is None:
            st.warning("Pending correction approval: revenue 130 to 120")
            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve financial correction demo"):
                st.session_state["financial_resume_result"] = finish_financial_resume_demo(test_session, pdf_bytes, True)
                st.rerun()
            if reject_col.button("Reject financial correction demo"):
                st.session_state["financial_resume_result"] = finish_financial_resume_demo(test_session, pdf_bytes, False)
                st.rerun()
        else:
            st.success("Offline SDK workflow completed. External API calls: 0.")
            st.write("Decision:", test_result["decision"])
            st.write("Final revenue:", test_result["corrected_revenue"])
            st.write("Financial review status:", test_result["review_status"])

    if st.button("Run FREE interruption demo"):
        try:
            report, validation, financial_data, agent_evaluation = (
                simulate_turn_limit(pages)
            )
            st.session_state["report"] = report
            st.session_state["validation"] = validation
            st.session_state["financial_data"] = financial_data
            st.session_state["agent_evaluation"] = agent_evaluation
            st.info(
                "Interruption with an unreviewed financial submission "
                "simulated. No OpenAI API credits used."
            )
        except ValueError as error:
            st.error(str(error))

    if st.button("Run FREE offline correction demo"):
        try:
            report, validation, financial_data, agent_evaluation = (
                simulate_conflict_correction(pages)
            )
            st.session_state["report"] = report
            st.session_state["validation"] = validation
            st.session_state["financial_data"] = financial_data
            st.session_state["agent_evaluation"] = agent_evaluation
            st.success(
                "Scripted offline correction completed. No OpenAI API "
                "credits were used. This does not test autonomous AI."
            )
        except ValueError as error:
            st.error(str(error))

    if st.button(
        "Analyse Company",
        type="primary",
        width="stretch",
    ):
        if not os.getenv("OPENAI_API_KEY"):
            st.error(
                "OPENAI_API_KEY is missing from .env"
            )
        else:
            with st.spinner(
                "Analysing the company report..."
            ):
                

                try:
                    report, validation, financial_data, agent_evaluation = run_due_diligence(
                        pages,
                        max_turns=8 if st.session_state.get('smoke_test_mode') else None,
                        inject_test_error=bool(st.session_state.get("inject_test_error")),
                        financial_approval_required=bool(st.session_state.get("real_financial_approval_mode")),
                        pause_pdf_bytes=pdf_bytes,
                    )
                    st.session_state["report"] = report
                    st.session_state["validation"] = validation
                    st.session_state["financial_data"] = financial_data
                    st.session_state["agent_evaluation"] = agent_evaluation
                    if (should_cache_report(bool(st.session_state.get("smoke_test_mode")))
                            and agent_evaluation["evaluation"] != "INTERRUPTED_TURN_LIMIT"):
                        save_report(
                            pdf_bytes,
                            report,
                            validation,
                            financial_data,
                        )
                    else:
                        st.info(
                            "Smoke-test result is session-only. "
                            "It has not replaced the cached full report."
                        )
                except SDKFinancialApprovalPaused as paused:
                    st.session_state["live_financial_pause"] = paused.handoff
                    st.warning(
                        "Actual SDK approval pause captured. Financial progress "
                        "was preserved in this session. Paid resume is disabled. "
                        "No finished due diligence report was created."
                    )
                except Exception as error:
                    st.error(
                        "Analysis failed: "
                        f"{type(error).__name__}: {error}"
                    )

        


    if "report" in st.session_state:
        validation = st.session_state.get("validation")


        st.subheader("4. Due diligence findings")
        agent_evaluation = st.session_state.get("agent_evaluation")
        if agent_evaluation and agent_evaluation.get("simulation"):
            st.info(
                "OFFLINE SIMULATION — predetermined tool steps, "
                "not a real AI model run. No API calls made."
            )
        if agent_evaluation:
            st.subheader("Agent investigation evaluation")
            if agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT":
                st.error(
                    "Investigation interrupted before a final AI report. "
                    "Submitted numbers may be unverified; this is not a pass."
                )
            elif agent_evaluation["evaluation"] == "PRELIMINARY_PASS":
                st.success(
                    "Financial evidence and tool sequencing passed "
                    "preliminary automated checks. Human validation "
                    "is still required."
                )
            else:
                st.warning(
                    "Outstanding investigation checks require review "
                    "before relying on the findings."
                )
            st.json(agent_evaluation)
            import json
            st.download_button(
                "Download investigation evaluation (JSON)",
                data=json.dumps(agent_evaluation, indent=2),
                file_name="agent_investigation_evaluation.json",
                mime="application/json",
            )
        else:
            st.caption(
                "No live tool-use evaluation is stored for this report. "
                "Cached analyses do not establish which tools were called."
            )

        current_financials = st.session_state.get("financial_data")
        current_review = (
            review_financial_evidence(pages, current_financials)
            if current_financials else None
        )
        notice_level, notice_message = final_verification_notice(
            current_financials, current_review
        )
        if notice_level == "warning":
            st.warning(notice_message)
        else:
            st.info(notice_message)
        st.markdown(st.session_state["report"])

    

        # Financial dashboard
        financial_data = st.session_state.get("financial_data")

        if financial_data and validation:
            year = int(financial_data["fiscal_year"])
            currency = financial_data["currency"]
            units = financial_data["units"]

            # Financial KPI cards
            st.subheader("Financial Overview")

            st.caption(
                f"FY{year} | {currency} | {units} | "
                "Arithmetic checks only"
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Revenue",
                f"{financial_data['revenue_current']:,.0f}"
            )

            col2.metric(
                "Revenue growth",
                f"{validation['revenue_growth']['calculated']:.2f}%"
            )

            col3.metric(
                "Gross margin",
                f"{validation['gross_margin']['calculated']:.2f}%"
            )

            col4.metric(
                "Net margin",
                f"{validation['net_margin']['calculated']:.2f}%"
            )

            # Revenue chart
            st.subheader("Revenue Comparison")

            revenue_chart = {
                f"FY{year - 1}": financial_data["revenue_previous"],
                f"FY{year}": financial_data["revenue_current"],
            }

            st.bar_chart(
                revenue_chart,
                x_label="Fiscal year",
                y_label=f"Revenue ({currency}, {units})",
            )

            # Additional financial diagnostics based on available inputs.
            extended_data = ExtendedFinancialData(
                revenue_current=financial_data["revenue_current"],
                revenue_previous=financial_data["revenue_previous"],
                gross_profit=financial_data["gross_profit"],
                net_income=financial_data["net_income"],
                operating_income=financial_data.get("operating_income"),
                operating_cash_flow=financial_data.get("operating_cash_flow"),
                capital_expenditure=financial_data.get("capital_expenditure"),
                subscription_revenue=financial_data.get("subscription_revenue"),
            )

            insights = calculate_financial_insights(extended_data)

            st.subheader("Financial Diagnostics")

            st.caption(
                "Calculated from the extracted financial inputs. "
                "Unavailable metrics indicate missing information, "
                "not zero values. Source accuracy requires separate "
                "verification."
            )

            diagnostic_labels = {
                "revenue_growth": "Revenue growth",
                "gross_margin": "Gross margin",
                "net_margin": "Net margin",
                "operating_margin": "Operating margin",
                "operating_cash_conversion": "Operating cash conversion",
                "subscription_revenue_share": "Subscription revenue share",
                "free_cash_flow": "Free cash flow",
            }

            diagnostic_rows = []

            for metric, label in diagnostic_labels.items():
                value = insights[metric]

                if value is None:
                    display_value = "Unavailable"
                    status = "Missing required input"
                elif metric == "free_cash_flow":
                    display_value = f"{value:,.2f} {currency} {units}"
                    status = "Calculated"
                else:
                    display_value = f"{value:.2f}%"
                    status = "Calculated"

                diagnostic_rows.append({
                    "Indicator": label,
                    "Result": display_value,
                    "Status": status,
                })

            st.dataframe(
                diagnostic_rows,
                width="stretch",
                hide_index=True,
            )

            # Evidence-aware financial insights for management review.
            management_insights = generate_financial_summary(
                financial_data
            )

            st.subheader("Management Financial Insights")

            st.caption(
                "Preliminary observations derived from extracted "
                "financial inputs. These do not independently "
                "verify source figures or establish investment merit."
            )

            for number, insight in enumerate(management_insights, 1):
                with st.container(border=True):
                    st.markdown(
                        f"**{number}. {insight['title']}**"
                    )
                    st.write(insight["finding"])

                    st.markdown("**Why it matters**")
                    st.write(insight["implication"])

                    st.markdown("**Management action**")
                    st.write(insight["next_step"])


        # Source verification for the uploaded company
        st.subheader("Source Evidence Checks")

        st.caption(
            "Checks whether submitted financial figures "
            "appear on the cited PDF page. "
            "A matching number does not prove the "
            "correct metric, year, or units."
        )

        if financial_data:
            source_results = verify_financial_data(
                pages,
                financial_data,
            )

            # Stronger verification for gross profit:
            # accept approved alternative statement labels.
            gross_value = financial_data.get("gross_profit")
            fiscal_year = financial_data.get("fiscal_year")
            source_pages = financial_data.get("source_pages") or {}
            gross_page = source_pages.get("gross_profit")

            if (
                isinstance(gross_value, (int, float))
                and not isinstance(gross_value, bool)
                and isinstance(fiscal_year, int)
                and not isinstance(fiscal_year, bool)
                and isinstance(gross_page, int)
                and not isinstance(gross_page, bool)
            ):
                gross_check = verify_with_alternative_labels(
                    pages=pages,
                    value=gross_value,
                    page_number=gross_page,
                    labels=["Gross profit", "Gross margin"],
                    fiscal_year=fiscal_year,
                    column_index=0,
                )


                for result in source_results:
                    if result.get("Financial figure") == "Gross profit":
                        result["Result"] = gross_check["status"]

                        explanation = gross_check.get("reason", "")
                        matched_label = gross_check.get("matched_label")

                        if matched_label:
                            explanation += f" | Statement label: {matched_label}"

                        result["Explanation"] = explanation


            if source_results:
                st.dataframe(
                    source_results,
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.warning(
                    "No financial figures available "
                    "for source verification."
                )
        else:
            st.warning(
                "No structured financial data available "
                "for source verification."
            )


        # Automatic financial statement year verification
        st.subheader("Financial Statement Row & Year Check")

        st.caption(
            "Checks revenue against fiscal-year headings "
            "and financial statement rows. "
            "Experimental: complex PDF layouts require manual review."
        )

        if financial_data:
            source_pages = financial_data.get("source_pages") or {}
            fiscal_year = int(financial_data["fiscal_year"])

            revenue_checks = [
                (
                    "Current-year revenue",
                    financial_data["revenue_current"],
                    source_pages.get("revenue_current"),
                    fiscal_year,
                ),
                (
                    "Previous-year revenue",
                    financial_data["revenue_previous"],
                    source_pages.get("revenue_previous"),
                    fiscal_year - 1,
                ),
            ]

            stronger_rows = []

            for label, value, page, year in revenue_checks:
                if (
                    not isinstance(page, int)
                    or not 1 <= page <= len(pages)
                ):
                    result = {
                        "status": "NEEDS_REVIEW",
                        "reason": "Missing or invalid PDF page.",
                    }

                else:
                    result = verify_revenue_automatically(
                        page_text=pages[page - 1],
                        fiscal_year=year,
                        expected_value=value,
                    )

                stronger_rows.append({
                    "Metric": label,
                    "Fiscal year": year,
                    "Value": value,
                    "PDF page": page,
                    "Result": result["status"],
                    "Explanation": result["reason"],
                })

            # Verify gross profit and net income
            additional_checks = [
                ("Gross profit", "gross_profit"),
                ("Net income", "net_income"),
            ]

            for label, metric in additional_checks:
                page = source_pages.get(metric)
                value = financial_data.get(metric)

                if (
                    not isinstance(page, int)
                    or not 1 <= page <= len(pages)
                    or value is None
                ):
                    result = {
                        "status": "NEEDS_REVIEW",
                        "reason": "Missing figure or valid source page.",
                    }
                else:
                    result = verify_metric_automatically(
                        page_text=pages[page - 1],
                        metric=metric,
                        fiscal_year=fiscal_year,
                        expected_value=value,
                    )

                stronger_rows.append({
                    "Metric": label,
                    "Fiscal year": fiscal_year,
                    "Value": value,
                    "PDF page": page,
                    "Result": result["status"],
                    "Explanation": result["reason"],
                })


            st.dataframe(
                stronger_rows,
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(
                "Financial data unavailable for row-and-year checks."
            )

        st.subheader("Financial Validation Results")
        validation = st.session_state.get("validation")

        if validation:
            for metric, result in validation.items():
                status = result["status"]

                if status == "PASS":
                    st.success(
                        f"{metric}: PASS — "
                        f"Calculated {result['calculated']}%"
                    )
                elif status == "FAIL":
                    st.error(
                        f"{metric}: FAIL — "
                        f"AI reported {result['reported']}%, "
                        f"Python calculated "
                        f"{result['calculated']}%"
                    )
                else:
                    st.warning(f"{metric}: MISSING")
        else:
            if agent_evaluation and agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT":
                st.warning(
                    "The investigation stopped before arithmetic validation "
                    "was completed. Submitted figures remain unverified."
                )
            else:
                st.warning(
                    "Structured financial data was not "
                    "submitted. Validation unavailable."
                )

        st.caption(
            "PASS confirms arithmetic agreement only. "
            "It does not independently verify the "
            "underlying figures or PDF citations."
        )
        # Check the report's writing quality before download.
        quality_issues = (
            []
            if agent_evaluation and agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT"
            else check_report_quality(st.session_state["report"])
        )

        st.subheader("Report Quality Review")

        if agent_evaluation and agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT":
            st.info(
                "Full-report quality checks are skipped for an interrupted "
                "investigation. This is a progress summary, not a final report."
            )
        elif quality_issues:
            st.warning(
                f"{len(quality_issues)} potential report quality "
                "issue(s) detected. Review these before using "
                "the report professionally."
            )

            with st.expander("View quality warnings", expanded=True):
                for issue in quality_issues:
                    st.write(f"• {issue}")
        else:
            st.success(
                "No issues detected by the automated writing "
                "and structure checks."
            )

        st.caption(
            "These checks flag possible writing and structural "
            "issues. They do not verify financial figures, "
            "source citations or analytical conclusions."
        )


        # Generate a professional PDF from the saved analysis.
        try:
            pdf_bytes = generate_pdf_report(
                report=st.session_state["report"],
                financial_data=st.session_state.get("financial_data"),
                validation=st.session_state.get("validation"),
            )

            st.download_button(
                label="Download Professional PDF Report",
                data=pdf_bytes,
                file_name="due_diligence_report.pdf",
                mime="application/pdf",
                width="stretch",
            )

        except Exception as exc:
            st.error(
                f"PDF export unavailable: {exc}"
            )


        st.download_button(
            label="Download Due Diligence Report",
            data=st.session_state["report"],
            file_name="due_diligence_report.md",
            mime="text/markdown",
            width="stretch",
        )

        st.info(
            "Before using this report, check important "
            "figures, calculations and citations "
            "against the uploaded PDF."
        )

else:
    st.info("Upload a company PDF to begin.")
