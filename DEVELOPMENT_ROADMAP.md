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
