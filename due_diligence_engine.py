"""Investigation tools and SDK execution, independent of the Streamlit page."""
import re
from agent_financial_review import review_financial_evidence
from optional_financial_validation import validate_optional_financial_data
from investigation_control import submission_block_reason
from investigation_outcome import investigation_outcome
from investigation_guidance import investigation_next_actions
from tool_sequence_audit import assess_tool_sequence
from report_verification import finalise_dd_report
from audit_appendix import append_audit_appendix
from agent_evaluation import evaluate_agent_run
from run_limits import permitted_turn_limit
from correction_changes import financial_correction_changes
from revenue_narrative_check import find_reversed_revenue_arrows
from fault_injection import inject_first_submission_error
from interrupted_report import interrupted_report
from resume_transcript import extract_resume_input, inspect_replay_boundary
from sdk_resume_policy import classify_run_boundary
from sdk_pause_capture import capture_approval_pause, pause_public_status
from tool_state_rebinding import prepare_tool_state
from sdk_resume_gate import checked_resume_mode
from sdk_resume_once import consume_sdk_resume_state
from live_financial_pause_handoff import make_financial_pause_handoff, SDKFinancialApprovalPaused
from latest_review_gate import trusted_latest_review
from completion_boundary import enforce_completion_boundary
from io import BytesIO
from pypdf import PdfReader
from financial_validator import FinancialData, validate_financials
from financial_numbers import finite_number
from agents import Agent, Runner, function_tool
from financial_turn_policy import FinancialTurnHooks

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

def run_due_diligence(
    pages, max_turns=None, inject_test_error=False,
    restored_checkpoint=None, resume_pdf_bytes=None,
    financial_approval_required=False,
    sdk_resume_state=None, offline_scripted_model=None,
    pause_pdf_bytes=None, decision_request_sha256=None,
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
        page_read_events = prepared["page_read_events"]
        if any(event["page"] > len(pages) for event in page_read_events):
            raise ValueError("INVALID_PAGE_READ_HISTORY")

    else:
        financial_submission = {}
        page_read_events = []
        observed_tool_calls = []
        submission_attempts = {"count": 0}
        review_state = {
            "reviewed_count": 0, "status": None,
            "page_reads": 0, "reads_at_review": 0,
            "source_pages_since_review": set(),
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

Preserve negative signs for income, operating cash flow and changes in balances.
Capital expenditure and share repurchases represent non-negative cash spending.
When a statement shows those spending outflows in parentheses or with a minus,
reconcile their magnitudes explicitly; do not flip other metrics to positive.
        """


        required_values = (
            revenue_current, revenue_previous, gross_profit, net_income,
            reported_revenue_growth, reported_gross_margin, reported_net_margin,
        )
        if not all(finite_number(value) for value in required_values):
            return "Financial submission rejected: figures and percentages must be finite numbers."

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
            if refusal.startswith("SOURCE_RECHECK_REQUIRED"):
                observed_tool_calls.append("source_recheck_refused")
            return refusal

        if submission_attempts["count"] == 1:
            cited_pages = set(page_references.values())
            cited_pages.update(page for value, page in optional_metrics.values()
                               if value is not None and page is not None)
            missing = cited_pages - review_state["source_pages_since_review"]
            if missing:
                observed_tool_calls.append("source_recheck_refused")
                return ("SOURCE_RECHECK_REQUIRED: Read every cited correction page after "
                        "the failed review. Missing PDF pages: "
                        + ", ".join(str(page) for page in sorted(missing)))

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

        page_read_events.append({"tool_index": len(observed_tool_calls), "page": page_number})
        observed_tool_calls.append("read_page")
        review_state["source_pages_since_review"].add(page_number)
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
        if not financial_submission or submission_attempts["count"] == 0:
            # A diagnostic request is not a review of an accepted submission.
            # Preserve the empty checkpoint so a later approval can resume.
            observed_tool_calls.append("review_without_submission")
            result["next_actions"] = investigation_next_actions(result)
            return json.dumps(result, default=str)
        observed_tool_calls.append("review_submitted_financials")
        review_state["reviewed_count"] = submission_attempts["count"]
        review_state["status"] = result["status"]
        review_state["reads_at_review"] = review_state["page_reads"]
        review_state["source_pages_since_review"].clear()
        result["next_actions"] = investigation_next_actions(result)

        return json.dumps(result, default=str)

    agent = Agent(
        name="AI Due Diligence Analyst",
        model=offline_scripted_model if resume_mode in ("OFFLINE_SDK_RESUME", "OFFLINE_FRESH_RUN") else "gpt-5-mini",
        tools=[
            search_report,
            read_page,
            calculate_percentage,
            calculate_growth,
            submit_financial_data,
            review_submitted_financials,
        ],
        instructions="""
Call submit_financial_data and review_submitted_financials on separate turns,
each alone without other tool calls. Wait for each result before the next step.


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
    if resume_mode == "OFFLINE_SDK_RESUME":
        consume_sdk_resume_state(sdk_resume_state)
        from sdk_state_rebinding import rebind_offline_state
        sdk_resume_state = rebind_offline_state(
            sdk_resume_state, agent, expected_request_sha256=decision_request_sha256)
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
        hooks=FinancialTurnHooks(),
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
            page_read_events=page_read_events,
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
    sequence_audit = assess_tool_sequence(tool_calls, observed_tool_calls=observed_tool_calls)
    print("Tool sequence valid:", sequence_audit["sequence_ok"])
    if sequence_audit["issues"]:
        print("Sequence issues:", ", ".join(sequence_audit["issues"]))
    print("Investigation outcome:", audit["outcome"])
    evaluation = evaluate_agent_run(
        pages, financial_submission, tool_calls,
        submission_attempts["count"], review_state["reviewed_count"],
        review_state["status"], observed_tool_calls=observed_tool_calls,
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

    
    final_output = result.final_output
    evaluation["final_response_complete"] = isinstance(final_output, str) and bool(final_output.strip())
    if not evaluation["final_response_complete"]:
        evaluation["evaluation"] = "NEEDS_HUMAN_REVIEW"
        evaluation["issues"] = list(dict.fromkeys(
            evaluation["issues"] + ["FINAL_RESPONSE_MISSING"]
        ))
    report = final_output if isinstance(final_output, str) else ""
    final_review = trusted_latest_review(
        pages, financial_submission, submission_attempts["count"], review_state
    )
    report = finalise_dd_report(report, financial_submission, final_review)
    report = append_audit_appendix(report, audit, sequence_audit)
    narrative_issues = find_reversed_revenue_arrows(report, financial_submission)
    if narrative_issues:
        evaluation["narrative_issues"] = narrative_issues
        evaluation["issues"] = list(dict.fromkeys(
            evaluation["issues"] + ["REVENUE_NARRATIVE_CHRONOLOGY_CONFLICT"]
        ))
        evaluation["final_eligible"] = False
        if evaluation["evaluation"] == "PRELIMINARY_PASS":
            evaluation["evaluation"] = "NEEDS_HUMAN_REVIEW"
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

    evaluation["simulation"] = resume_mode in ("OFFLINE_SDK_RESUME", "OFFLINE_FRESH_RUN")
    completion = enforce_completion_boundary(
        report, financial_submission, submission_attempts["count"],
        review_state, evaluation,
    )
    report = completion["report"]
    evaluation["final_eligible"] = completion["final_eligible"]
    evaluation["completion_reason"] = completion["reason"]
    if not completion["final_eligible"]:
        validation_results = None

    return report, validation_results, financial_submission.copy(), evaluation
