# AI Due Diligence Agent — portfolio case study

**Project type:** Independent Python / Streamlit financial and technology due diligence prototype  
**Audience:** Investment, M&A, strategy, and technology due diligence teams  
**Current maturity:** Working offline prototype. Scripted acceptance tests pass; real-browser manual acceptance and live autonomous evaluation remain outstanding.

## 1. Problem and objective

An investment analyst reviewing an acquisition target may need to locate key financial statement figures, reconcile conflicting disclosures, assess preliminary financial and technology risks, and record what remains uncertain. An AI-assisted first pass could help organize this work, but an unsupported number or confident-sounding source claim can mislead a decision.

I built this project to explore a controlled alternative: **make financial submissions reviewable, grounded in cited source pages, and subject to explicit human decisions**, rather than treating an AI response as a verified investment conclusion.

## 2. What I built

The application combines:

| Layer | Implementation | Purpose |
| --- | --- | --- |
| Document intake | Streamlit, Python, `pypdf` | Accept text-based annual-report PDFs and extract page text |
| Financial checks | Financial validation and derived-metric modules | Test calculations and highlight missing or inconsistent figures |
| Source review | PDF page citations and financial statement row/year checks | Distinguish finding a number from verifying the correct row and period |
| Orchestration | OpenAI Agents SDK with an offline scripted model | Exercise source reads, financial submissions, reviews, and approval pauses |
| Human control | Financial approval previews and explicit approve/reject decisions | Require a reviewer to inspect proposed figures before the scripted workflow resumes |
| Reporting | Preliminary due diligence views and report-generation modules | Present findings with qualifications; keep simulated/incomplete outputs out of final exports |
| Verification | Python unit tests, Streamlit AppTests, offline integration, network-blocked acceptance | Exercise defined behaviors without spending model credits |

**Architecture at a glance**

```text
Annual-report PDF
  -> text extraction (page-aware)
  -> financial submission + source citations
  -> arithmetic and statement-row/year evidence checks
  -> reviewer preview (proposed vs previously accepted)
  -> explicit approve / reject
  -> controlled scripted resume and correction
  -> preliminary outcome or read-only incomplete state
```

The SDK-based offline rehearsal exercises the application's tool and pause/resume wiring, **not** independent autonomous financial reasoning.

## 3. Demonstrable example: conflicting revenue figures

A fully synthetic two-page PDF deliberately introduces conflicting FY2025 revenue information:

| Evidence | Figure | Interpretation |
| --- | --- | --- |
| PDF page 1 | USD 130 million | Provisional/misleading headline |
| PDF page 2 | USD 120 million | Authoritative figure in the synthetic financial statement |

In the **Standard correction** rehearsal, a scripted proposal initially submits 130. A reviewer can examine the proposal, its citations, and the local checks. Deliberately accepting this initial *test* submission exercises the error-correction sequence; it does **not** represent an acceptable practice for real due diligence. After the scripted workflow checks the relevant source again, the next approval preview compares the previously accepted 130 with the proposed correction of 120.

The reviewer must make another explicit decision. If approved and the scripted checks complete, the displayed result reports the synthetic 120 figure. If rejected, the workflow ends without silently accepting the correction.

Other offline rehearsal scenarios include reading an unrelated source page before recovery, removing an unsupported optional cash-flow metric rather than inventing zero, and stopping when a limited scripted request allowance is exhausted.

## 4. Key engineering decisions

**Financial data is not automatically trusted.** Calculations, page citations and statement-row/year matches are separate checks. An apparent numeric match on a page does not alone establish correct period, metric, or accounting meaning.

**Approvals are specific to the pending proposal.** The displayed approval request is fingerprinted. A stale or changed request cannot be approved using an earlier preview.

**Failure is visible, not disguised as completion.** Interrupted runs retain inspectable progress where safe, but incomplete rehearsals do not become verified final reports or download options.

**Missing values stay missing.** An unsupported metric can be removed explicitly instead of being forced to zero, which would create a misleading analysis.

**Free testing is isolated from paid analysis.** The scripted workflow uses synthetic data with no provider model calls. The separate **Analyse Company** path can invoke paid API usage and is not part of the free demonstration.

## 5. What has and has not been validated

| Area | Current evidence |
| --- | --- |
| Deterministic synthetic approval/correction/rejection flows | Automated offline tests and CI |
| Streamlit component interactions | Automated AppTests (not a real-browser walkthrough) |
| Synthetic financial statement conflict | Local fixture preflight and scripted acceptance |
| External API activity in the guarded tests | Zero external API calls reported |
| Real-browser human acceptance | **Not completed** |
| Autonomous model reasoning on arbitrary company filings | **Not validated** |
| Production security, confidential deal deployment, durable multi-user approvals | **Not validated** |

These results provide evidence of **tested workflow controls**, not accuracy guarantees, performance improvements, investment returns, or a security certification.

## 6. How to demonstrate it safely

Use the existing feature branch `feature/controlled-financial-corrections` and the detailed instructions in [OFFLINE_DEMO.md](OFFLINE_DEMO.md). The short path is:

```bash
source .venv/bin/activate
python -m offline_demo_preflight --workflow
python -m portfolio_demo_card --output demo-card.md
python scripts/create_conflict_test_fixture.py
python -m streamlit run app.py
```

Upload `synthetic_conflict_test.pdf`, open **FREE application correction workflow**, and choose **Standard correction**. Compare the two source pages, inspect the proposed/previous values and local review findings, and deliberately run the controlled correction rehearsal. Do **not** click **Analyse Company** when demonstrating the zero-credit path.

The generated `demo-card.md` provides a human-readable record of the synthetic checks. It intentionally marks manual browser and autonomous model validation as **NOT RUN**. The card is not a final due diligence report.

## 7. Next steps and learning

The highest-priority remaining task is a **human walkthrough in a real Streamlit browser**, followed by fixes to any confusing screens. Controlled paid-model evaluation requires a separately approved budget and explicit authorization before any provider calls. Before using real confidential transaction documents, the project would also need stronger privacy, authorization, storage and deployment controls.

**Portfolio takeaway:** Financial AI is most useful when the workflow can show *where a figure came from, what was actually checked, who approved a change, and what remains unverified*. This prototype demonstrates those design principles using a free, reproducible synthetic case.
