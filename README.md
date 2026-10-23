# AI Financial & Technology Due Diligence Agent

A Python and Streamlit prototype that turns company annual-report PDFs into a **preliminary, evidence-led investment due diligence briefing**. Designed as a portfolio project demonstrating the application of agentic AI, financial analysis, source checking, and digital/technology diligence in a private-equity or M&A workflow.

> **Status:** Working local prototype, tested with Adobe and Microsoft FY2025 annual reports. Outputs are decision-support material, **not** a substitute for professional financial, legal, commercial, or technical due diligence.

## Why I built it

Reviewing a target company's public filings can be time-consuming. This project explores how an AI-assisted workflow can accelerate the first pass while making underlying assumptions, calculations, and source limitations visible to an analyst.

Its guiding question is: **What do the reported numbers and disclosures suggest about an investment opportunity, what remains uncertain, and what should an investment team validate next?**

## Core capabilities

- **PDF ingestion:** Read text from an uploaded annual report using `pypdf`.
- **Structured extraction:** Capture selected financial metrics and source page references through an OpenAI Agents SDK workflow.
- **Financial analysis:** Calculate growth, profitability, operating cash flow, indicative free cash flow and selected multi-year trends, when the underlying figures are available.
- **Diligence commentary:** Generate a preliminary briefing covering financial, commercial and technology considerations, risks, and follow-up diligence questions.
- **Layered source checks:** Distinguish between a figure appearing on a cited page and a stronger match to a specific financial-statement row and fiscal-year column.
- **Alternative terminology:** Support approved statement-label variants; for example, Adobe reports **Gross profit** and Microsoft reports **Gross margin** as a monetary statement row.
- **Results interface:** Review findings and verification statuses in Streamlit.
- **PDF output:** Produce a formatted diligence briefing for review or sharing.
- **Local report reuse:** Reload saved analyses where available, avoiding unnecessary repeat model calls.

## Technology stack

| Component | Technology |
|---|---|
| Application interface | Streamlit |
| Core language | Python |
| PDF text extraction | `pypdf` |
| AI orchestration | OpenAI Agents SDK |
| AI model | Configurable through the project; developed with `gpt-5-mini` |
| Report generation | ReportLab |
| Environment configuration | `python-dotenv` |
| Tests | Python `unittest` |

## How the workflow works

```text
Annual-report PDF
       |
       v
PDF text extraction
       |
       v
AI-assisted extraction + diligence assessment
       |
       +----> Structured financial values + cited PDF pages
       |              |
       |              v
       |       Derived ratios and trend analysis
       |              |
       |              v
       |       Source evidence checks
       |
       v
Diligence findings and review flags
       |
       v
Streamlit dashboard + downloadable PDF report
```

### Evidence-verification levels

| Status | Interpretation |
|---|---|
| `ROW_YEAR_MATCH` | Value matched a recognized financial-statement row and fiscal-year column on the referenced PDF page under the checker's parsing assumptions. |
| `NUMBER_FOUND` | Value appears on the referenced page, but the metric label, year and units have **not** been established by that check alone. |
| `NEEDS_REVIEW` | Supporting evidence is missing, ambiguous, inconsistent or not recognized by the parser; a human should investigate. |

A match is **not** an audit opinion or proof that the underlying filing or AI interpretation is correct. Complex tables, OCR/scanned documents, unconventional layouts, accounting conventions, and ambiguous labels can require manual review.

## Example validation

The prototype was exercised with two FY2025 public-company annual reports. The following values are in **USD millions**.

| Company | Metric | FY2025 | FY2024 |
|---|---|---:|---:|
| Adobe | Revenue | 23,769 | 21,505 |
| Adobe | Gross profit | 21,218 | 19,147 |
| Adobe | Net income | 7,130 | 5,560 |
| Microsoft | Revenue | 281,724 | 245,122 |
| Microsoft | Gross margin (reported monetary row) | 193,893 | 171,008 |
| Microsoft | Net income | 101,832 | 88,136 |

**Observed verification checks:** Four selected financial-statement row/year checks passed against Adobe's FY2025 annual report (PDF page 50), and four passed against Microsoft's FY2025 annual report (PDF page 36). The alternative-label helper also successfully matched Adobe's `Gross profit` and Microsoft's `Gross margin` rows. The project ran **33 passing unit tests** at the latest reported checkpoint.

These checks establish behavior on the selected examples, **not universal accuracy** across companies or filings.

## Running locally

### Prerequisites

- Python 3 and a working virtual environment
- An OpenAI API key with available API usage, for analyses that invoke the model
- The project's Python dependencies installed in the virtual environment

On macOS, from the project folder:

```bash
cd ~/Desktop/AI-Due-Diligence
source .venv/bin/activate
python -m streamlit run app.py
```

Open the local URL shown in Terminal, generally `http://localhost:8501`.

If dependencies have not yet been installed, install them within your virtual environment according to the project's dependency manifest, if present. Main libraries used include `streamlit`, `pypdf`, `reportlab`, `python-dotenv`, and the OpenAI Agents SDK.

### Configure the API key

Create a local `.env` file in the project directory with:

```dotenv
OPENAI_API_KEY=your_api_key_here
```

Never commit `.env`, credentials, or confidential target-company reports to a public repository. API calls can incur usage charges. Loading an existing saved analysis and generating reports locally may avoid a fresh paid analysis.

### Run tests

```bash
python -m unittest discover -s tests -t . -v
```

A passing test suite demonstrates the tested behaviors, but does not eliminate model hallucinations or all extraction errors.

## Project structure (selected files)

```text
AI-Due-Diligence/
├── app.py                          # Streamlit UI and workflow
├── financial_insights.py           # Calculated financial insights
├── financial_summary.py            # Structured financial commentary
├── financial_validator.py          # Arithmetic and consistency checks
├── optional_financial_validation.py
├── source_verifier.py              # PDF-page and statement-row checks
├── report_quality.py               # Heuristic report-quality checks
├── pdf_report.py                   # Downloadable report generation
├── report_storage.py               # Save/load analysis results
├── tests/                          # Unit tests
└── .env                            # Local secrets; do not commit
```

Additional helper modules support financial-label matching and year-column detection. Some local backup/test report files may be present during development.

## Design choices and limitations

1. **Public filings are only a starting point.** Annual reports do not provide all evidence required for a transaction, particularly customer cohorts, quality of earnings, contracts, technical architecture, security controls, and management plans.
2. **Calculated free cash flow is indicative.** Operating cash flow minus cash capital expenditure is not normalized transaction cash flow. Differences in accounting policies and one-off items matter.
3. **Source validation is layered, not absolute.** `NUMBER_FOUND` is a weaker result than `ROW_YEAR_MATCH`; even a row/year match depends on successful PDF parsing and correct unit interpretation.
4. **Some inputs are optional.** When a measure is missing, the app should disclose that gap rather than invent a value or force a cross-company comparison.
5. **Generative analysis requires judgment.** Investment conclusions and technology-risk interpretations should be reviewed, challenged and corroborated against primary evidence.
6. **The app is a prototype.** It is not production-hardened for confidential deal materials, access control, security assurance or regulatory compliance.

## Potential next improvements

- More systematic regression coverage of alternative row labels and different PDF layouts.
- Stronger end-to-end evaluation of citations and numeric claims in the generated narrative.
- Standardized reporting of confidence and evidence gaps across every extracted metric.
- Secure deployment controls and handling of sensitive transaction data.

## Portfolio walkthrough

A short demonstration can show: **(1)** upload a public annual report; **(2)** inspect extracted financial metrics and derived trends; **(3)** show the verification table, highlighting `ROW_YEAR_MATCH` versus `NUMBER_FOUND`; **(4)** review the diligence narrative and open questions; and **(5)** download the PDF briefing.

**Project takeaway:** Agentic AI can help structure and accelerate early-stage deal screening when it is paired with transparent calculations, traceable evidence, explicit uncertainty and human review.

## Offline approval-to-resume development

`financial_approval_resume.decide_and_resume_offline` connects a document-bound
financial approval handoff to the actual app's SDK resume path. It applies the
reviewer's decision, extracts source text from the same PDF, restores financial
counters, and uses the SDK's in-memory serialization interface to resolve pending
calls against rebuilt application tools. A further approval pause returns a new
handoff; failures consume the old handoff and are not retried automatically.

Only the exact `ScriptedOfflineModel` implementation is accepted. These runs test
SDK orchestration and financial controls, not autonomous model reasoning. Results
are marked as simulations and cannot qualify for final report export. No snapshot
is written to disk. The existing one-shot resume guard remains process-local;
independent copies or restarts are not protected by durable idempotency.

Live paid-model continuation remains disabled. It requires separate authorization
and validation before enabling. Development remains on the open feature branch.

### Rehearse the complete correction loop without API credits

Use the synthetic conflict PDF generated by
`python scripts/create_conflict_test_fixture.py`. From a Python session in the
repository, the following exercises the actual application's submission, source
reread, review, and completion controls with a scripted SDK model:

```python
from pathlib import Path
from offline_correction_workflow import start_offline_correction_workflow
from financial_approval_resume import decide_and_resume_offline

pdf = Path("synthetic_conflict_test.pdf").read_bytes()
session = start_offline_correction_workflow(pdf)
# First explicit approval accepts the deliberately wrong synthetic revenue, 130.
paused = decide_and_resume_offline(session["handoff"], pdf, True, session["model"])
# The app detects the mismatch, rereads page 2, and pauses before correcting it.
print(paused["handoff"]["checkpoint"]["review_status"])  # NEEDS_REVIEW
result = decide_and_resume_offline(paused["handoff"], pdf, True, session["model"])
print(result["financial"]["revenue_current"])  # 120
print(result["evaluation"]["evaluation"])  # PRELIMINARY_PASS
```

Set the second decision to `False` to reject the correction: the original 130
remains, and completion checks keep the report incomplete. The rehearsal is
restricted to the synthetic fixture, marks results as simulations, and never
qualifies them for final report export. Automated coverage blocks socket
connections while running this full workflow.

### Try the workflow in Streamlit

Upload `synthetic_conflict_test.pdf` and select **Start FREE application workflow**.
Use **Approve and continue FREE workflow** for the initial synthetic figures,
then inspect the failed source review before approving or rejecting the proposed
correction. Each pending request requires its own decision. The rehearsal uses
no paid model and leaves existing analysis results untouched. Changing the
uploaded PDF clears the session; **Discard FREE application workflow** removes it
explicitly. Rehearsal results have no final-report download.

`due_diligence_engine.py` holds the investigation tools independently of the
Streamlit page. Resuming a workflow no longer imports or renders the page.

Checkpoint review tracking identifies the latest accepted submission that was
reviewed, rather than counting every review invocation. Repeated reviews survive
an approval pause, and the most recent review sets the source-reread boundary.
A review requested before any accepted submission remains diagnostic only and
cannot establish verified financial state. Restoring a trace with a review before
its submission, or a false claim that the latest submission was reviewed, fails.

The offline approval interface previews the actual pending SDK financial request,
including proposed amounts, earlier accepted amounts, currency, fiscal year, and
PDF page references. A fingerprint covers the call identity and all arguments.
If a request changes after it was shown, the current click is rejected before any
SDK decision; the refreshed proposal requires a new decision. Financial approvals
reject unexpected tools, duplicate argument keys, malformed JSON and non-finite
values. This binding does not provide cross-process persistence or authentication.

## Full-engine evaluation checkpoint

Run `python -m offline_evaluation` for a compact JSON summary and a nonzero exit
code if a workflow check fails. CI runs this alongside the unit tests. It creates
its own temporary synthetic PDF, starts in the actual application engine, reads
the source through the app tool, pauses before the first submission, exercises
both reviewer decisions, and checks the final result. There is no bootstrap
agent or fabricated initial source-read history in this rehearsal.

The JSON distinguishes `SCRIPTED_OFFLINE_FULL_ENGINE` from autonomous model
validation, which remains `NOT_RUN`. Paid continuation remains disabled. The
remaining live-test inputs are an explicitly approved public or synthetic test
PDF and an agreed API spending limit; a turn cap alone is not a monetary cap.
No real-model investigation or paid continuation is launched by this command.

## Paid-test preparation: no API calls

The agreed test document is `synthetic_conflict_test.pdf`. The original **£5 API
budget includes all prior usage**; it is not a fresh allowance for another test.
Every paid test requires separate explicit permission. No new funding or
automatic top-up is authorized by preparing a plan.

Use the Streamlit **Prepare a paid test — estimate only, no API call** panel, or:

```bash
python -m paid_test_planning synthetic_conflict_test.pdf
# Optional: replace the example balance with the actual current USD credit.
python -m paid_test_planning synthetic_conflict_test.pdf --remaining-credit-usd 1.00
```

Blank credit stays unknown. The planner does not read credentials, retrieve an
account balance, perform currency conversion, or execute an investigation. A
reported balance is not treated as verified. An ample balance never authorizes
execution: `can_execute` is always false, and paid continuation remains disabled.

The default proposal is 8 model requests across the whole test, at most 16,000
input tokens and 2,048 output tokens per request. These ceilings do not reset at
approval. Using the [official GPT-5 Mini pricing](https://developers.openai.com/api/docs/models/gpt-5-mini)
checked on 23 October 2026 ($0.25 input and $2.00 output per million tokens), the
conditional token-cost estimate is **$0.064768**, with a doubled, upward-rounded
planning reserve of **$0.13**. This assumes all requests fit those planned limits,
ignores cached-input discounts, and is **not an enforced spending cap**. Live
request accounting and model availability still need validation before any paid
execution. The current documentation marks GPT-5 Mini deprecated; the planner
records that fact rather than silently replacing the configured model.

For platform-level controls, [OpenAI's spend-limit documentation](https://developers.openai.com/api/docs/guides/spend-limits)
distinguishes alerts from enforced limits and notes that enforcement can lag.
The app does not claim these settings guarantee an exact lifetime £5 ceiling.
Confirm the actual remaining credit and currency before proposing a paid run;
then seek permission for that specific run. Never interpret a financial-submission
approval inside an investigation as permission for additional paid model usage.

## Practice incomplete investigations without API credits

Run `python -m practice_scenarios` to create a temporary synthetic PDF and run
nine failure scenarios through the actual application engine. Alternatively,
upload `synthetic_conflict_test.pdf` in Streamlit and select **Run FREE practice
suite**. These rehearsals are independent of real analysis and paid-test plans.

The scenarios cover premature final output, reversed revenue chronology in the narrative,
a skipped review, swapped fiscal-year
values, incorrect source-page citations, missing monetary units, a replacement
with an optional value but no source page, and turn limits both before submission
and after review. Each check requires the report to remain incomplete and
ineligible for final export; a rejected replacement must retain earlier figures.
`PASS` means the expected failure behavior occurred, not that the investigation
produced a valid report. Scripts exercise local SDK tools and financial controls;
real model reasoning is still untested. CI runs this suite, and unit tests execute
it with socket connections blocked. No paid test is started and no credit balance
is required.

A detected reversal of verified revenue chronology now changes a preliminary pass
to `NEEDS_HUMAN_REVIEW`, blocks completion and final-export eligibility, and keeps
the specific chronology warning in the incomplete report. Numeric verification
alone cannot override that known narrative conflict. This check recognizes the
supported revenue-arrow patterns; it is not a complete natural-language fact checker.

The chronology check requires a revenue label on the arrow's line or an immediate
revenue heading. An unrelated cash-flow arrow using the same numbers is not
classified as a revenue contradiction.

A corrected submission can also pause before its own review runs. Restoration
preserves the new figures with an empty latest-review status while retaining the
prior reviewed-submission count. Earlier feedback cannot validate the correction.
The full-engine evaluation rehearses this additional pause and confirms that a
third submission still cannot replace the corrected figures, even if approved.

The offline approval screen also shows the cited PDF page text in **Source evidence
for pending figures**. Reviewers can compare amounts, statement labels and year
columns before recording a decision. Opening the evidence preview does not call
or resume a model or accept the pending figures.
