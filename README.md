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
