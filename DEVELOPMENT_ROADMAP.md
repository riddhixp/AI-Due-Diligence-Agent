# Remaining work toward a portfolio demonstration

The PDF app, financial/source checks, approval controls and scripted SDK
approval-to-resume workflow are implemented. Paid continuation remains disabled.
Offline tests establish code behaviour, not autonomous model reasoning.

These are planning estimates for active development and testing, not a delivery
promise or work scheduled between chat sessions. Approval delays, unavailable
credits and findings from live tests can extend elapsed time.

| Step | Outcome | Estimated effort | User input |
| --- | --- | --- | --- |
| 1. Finish free rehearsal acceptance | Shared proposal diagnostics, free success/rejection/recovery paths, automated UI checks | About half a working day | Try the free rehearsal locally; report confusing screens or errors |
| 2. Prepare a controlled live test | Review model configuration, enforce conservative request/output limits and a stop condition, surface usage and failures, keep live testing gated | 1–2 working days | Confirm remaining balance within the original £5 deposit and explicitly approve a specific paid test |
| 3. Validate live reasoning and continuation | Run an approved PDF investigation, inspect proposal, approve/reject, verify resumed tool order, sources, result and actual usage | Half to one working day initially; allow 1–2 more for fixes | Approval before any paid run; review financial findings |
| 4. Package the portfolio demo | Repeatable setup, short walkthrough, example output and documented limitations | About half a working day | Confirm the demo is understandable and acceptable |

Allow roughly 3–6 focused working days for a demonstrable prototype, depending on
live-test findings and permission/credit availability. Completing all offline
work does not mean the live agent is validated. If the remaining budget cannot
cover an approved test, retain the offline demo and record live validation as
outstanding; do not spend beyond the existing budget.

A reliable hosted product is a separate scope: authentication, document privacy
and retention, durable approval/idempotency across restarts or servers, monitoring,
load testing and deployment. Estimate that only after choosing the hosting and
usage requirements; it is likely weeks of additional work.

## Current controlled-test preparation

A process-local model-request budget is implemented and exercised with the actual
SDK offline approval/resume workflow. The same quota survives both approval
pauses; concurrent reservations cannot exceed it and failed requests do not
refund a reservation. Exhaustion blocks the next model dispatch, preserves any
accepted-but-unreviewed tool progress and cannot create a final report.

This budget is currently wired only into the scripted model. It does not limit
paid providers, provider-internal retries, input/output tokens, or billing. Live
integration, per-request token bounds, retry policy, usage reporting and explicit
authorisation remain outstanding before any paid continuation can be considered.
Creating a fresh budget object resets its quota; trusted orchestration must keep
one object for the entire test. Restart/server durability remains separate work.

## Paid-test planning verification gate

The offline plan displays whole-workflow input/output token totals calculated
from the selected request count and per-request assumptions. These totals are
planning figures only; they are not measured usage or enforced provider limits.

The offline cost planner now always identifies unverified model availability
and pricing requiring revalidation as explicit blockers, even when a large
remaining credit amount is entered. Its cached USD estimate is illustrative
only, not a current price quote or spend cap. This does not call a provider,
enable paid continuation, or grant permission to spend the original GBP budget.
Before any paid test, independently verify the currently supported model,
current pricing and remaining credit, then request explicit test-specific
authorization. Live token, request, retry and billing enforcement remain
unfinished.

## Offline simulated token ledger

A separate `SimulatedTokenLedger` can now accumulate explicitly simulated
input/output token counts atomically and reject an over-limit record without
partially updating totals. It includes concurrency and validation tests. It is now optionally wired into the SDK scripted model using fictional one-input\nand one-output token per scripted response; the connection is exercised in unit\ntests. Counts are neither measured from SDK responses nor displayed in the app.
Two offline integration tests now exercise the same ledger through the full
approval/correction sequence (seven fictional requests) and a six-token stop
at the last resume. An exhausted rehearsal remains incomplete, not exported. The final review tool
may already have returned PRELIMINARY_CHECKS_PASSED before the scripted token
limit stops the final model response; a passing review never substitutes for a
completed investigation and must not unlock a final artifact.
 It cannot account
for network retries, missing usage responses or provider billing; real model
execution remains disabled pending permission and verified enforcement.

## Free manual acceptance check

Use the generated synthetic conflict PDF, not a confidential company document.
Run `python scripts/create_conflict_test_fixture.py` to create
`synthetic_conflict_test.pdf` in the project folder. Upload that file, then use the
free workflow in the app. Start the app with `streamlit run app.py` from the activated environment.
Open **FREE application correction workflow** without starting **Analyse Company**.

1. Start the standard free rehearsal. Confirm the incorrect proposed revenue is
   flagged before approval and no accepted submission is shown yet.
2. Approve the first proposal. Confirm the correction preview shows previous
   revenue 130 and proposed revenue 120 with local preliminary checks passing.
   The previous accepted figure must stay 130 until the second decision.
3. Approve the correction. Confirm synthetic revenue is 120, external API calls
   are zero, and the result is labelled as a scripted rehearsal.
4. Restart, approve the first proposal, then reject the correction. Confirm the
   failed evidence/incomplete result remains visible instead of a verified report.
5. Try source-read recovery and unsupported-cash-flow removal. Check that recovery
   requires a new approval and removed cash flow stays missing, rather than zero.
6. Discard the rehearsal and remove the PDF. Confirm the transient rehearsal and
   its decisions disappear and an existing real analysis was not overwritten.

If something differs, record the scenario, last clicked button and visible error.
Never include API keys or confidential PDF contents in an error report.

No merge into main or paid test is authorised by this roadmap.

## Repeatable offline acceptance

`python -m offline_acceptance` now combines the workflow and failure-practice
suites under a Python socket network guard, including imports. Any attempted
connection fails acceptance even when caught by a scenario. This supports free
local acceptance and CI; it does not validate autonomous reasoning or authorise
a paid run. See README for the guard's scope and limitations.

## Synchronous SDK restoration lifecycle

Offline state restoration reuses the thread-default event loop owned by SDK
`run_sync`, rather than clearing it with a separate `asyncio.run`. Repeated
approval resumes retain the same loop, including after restoration errors.
Calling the synchronous restoration helper inside an active async context is
rejected before creating the restoration coroutine. This does not enable live
continuation or introduce background execution.

## Visible rehearsal request allowance

The free application rehearsal now uses one 12-request allowance across every
approval pause and displays used and remaining requests. A fresh rehearsal gets
a fresh allowance. Standard correction uses seven scripted model requests; the
source-read recovery scenario uses nine. Exhaustion still blocks further model
dispatch and preserves failure progress for inspection. This does not meter
tokens or money and does not enable paid providers.

### Free request-limit stop rehearsal

Select **Stop at the request limit**, start the free workflow, and approve both
proposals. The five-request allowance then stops the next model dispatch.
Expected: an allowance-exhausted message, revenue 120 retained as unreviewed
progress, no decision controls, and no final report export. Starting a new
standard rehearsal creates a fresh 12-request allowance. Switching the selector
alone does not change the active rehearsal's allowance.

The one-command acceptance run also checks request-limit exhaustion through the
real engine: no sixth model dispatch, preservation of the accepted unreviewed
correction, and refusal to retry the failed handoff without consuming its script.
These checks run alongside approval, rejection, source-read recovery and optional
metric removal. They remain scripted evidence only.

## Offline demo handoff

The current free workflow is packaged in [OFFLINE_DEMO.md](OFFLINE_DEMO.md),
including standard correction, rejection and request-limit stop walkthroughs.
Automated acceptance passes, but manual usability acceptance is pending. Local
commits still require permission to publish to the development branch before
the user's Mac can obtain them from GitHub. Paid-provider integration and token,
retry and billing controls remain separate unfinished work; the free demo is
not evidence that those controls are implemented.
