# Free portfolio demo and tester handoff

This walkthrough demonstrates the application engine, source checks and human
approval controls with a deterministic script. It uses synthetic figures and no
paid model. Autonomous reasoning and paid continuation remain unvalidated.

## Prepare the current development version

Use branch `feature/controlled-financial-corrections`. Development changes
are committed to the GitHub branch; an older Mac checkout needs to fetch them
before running the latest checks. From the project folder, first run:

```bash
git fetch origin
git switch feature/controlled-financial-corrections
git pull --ff-only origin feature/controlled-financial-corrections
```

Do not merge PR #1 or switch to `main` for this rehearsal.

From the project folder with its dependencies installed:

```bash
source .venv/bin/activate
python -m offline_acceptance --summary
python scripts/create_conflict_test_fixture.py
python -m streamlit run app.py
```

The acceptance command should report PASS for both suites and zero blocked
network attempts. An API key is not needed for these scripted exercises.

For current GitHub verification, check all three jobs in the PR's **Python tests**
workflow: `unit-tests`, `offline-integration`, and `offline-network-acceptance`.
A green integration job alone is not sufficient to claim the whole pipeline
passed. The CI workflow clears OpenAI API credentials before running all jobs;
no paid model credentials are required for the scripted checks. Cancelled, queued and in-progress jobs remain unverified. The
network-blocked check is a scripted Python socket guard, not a guarantee that
an unrelated production analysis path cannot access the internet.
Open the local URL printed by Streamlit and upload `synthetic_conflict_test.pdf`.
Use **FREE application correction workflow**. **Analyse Company** invokes a
separate analysis path and is outside this free walkthrough.

## Five-minute demonstration

1. Select **Standard correction** and start the free workflow. The initial
   proposal is revenue 130, while the authoritative statement shows 120. Point
   out the proposed figures, source text and local evidence findings.
2. Approve the first proposal to deliberately exercise correction handling.
   This is a synthetic test choice, not advice to approve unsupported real data.
   The next preview compares previously accepted revenue 130 with proposed 120.
   The first figures remain accepted until the second decision.
3. Approve the correction. Show synthetic revenue 120, completed scripted checks
   and seven of twelve requests used. The result remains a rehearsal and has no
   final due-diligence export.
4. Start again and reject the correction. Show the incomplete outcome and the
   retained previous figures.
5. Select **Stop at the request limit**, start again and approve both proposals.
   Show the five-request stop, retained revenue 120 and incomplete latest review.
   There is no retry button or final export. A new standard rehearsal can start.

## Additional acceptance cases

| Scenario | Expected observation |
| --- | --- |
| Recover after unrelated source read | Wrong-page read cannot unlock a correction; the proper read leads to a new approval request. |
| Remove unsupported cash flow | Preview discloses removal; approved removal clears both value and citation; missing diagnostics do not become zero. |
| Discard rehearsal | Pending rehearsal disappears; existing real analysis remains separate. |
| Remove uploaded PDF | Document-bound transient results and approval state are cleared. |

Changing the scenario selector alone does not replace an active run. Press Start
for a new run. Request allowances are process-local controls for the scripted
model; they are not token counts, billing caps or a durable production budget.

## Manual Streamlit acceptance checklist

The automated CI tests do not click through the Streamlit interface. Before
showing this to an interviewer, complete this checklist with the synthetic PDF:

- [ ] **Standard correction:** initial proposed revenue 130 is visible with its
  source, and the reviewer must explicitly approve it.
- [ ] **Correction preview:** revenue changes to proposed 120 only after
  reading the authoritative second page; previously approved figures remain
  unchanged until the second approval.
- [ ] **Approval:** the finished rehearsal retains revenue 120 and explicitly
  identifies itself as simulated, not a final investment recommendation.
- [ ] **Rejection:** declining a correction leaves the earlier accepted values
  intact and marks the latest review incomplete.
- [ ] **Request limit:** hitting five scripted model requests produces an
  incomplete state with no retry of the consumed handoff.
- [ ] **Source recovery and optional removal:** wrong-page evidence cannot
  resolve the conflict; approved cash-flow removal clears both value and source.
- [ ] **Session cleanup:** discard or remove the PDF, and confirm the pending
  rehearsal does not reappear on rerun or a new upload.
- [ ] **Export guard:** an incomplete or simulated rehearsal cannot be
  downloaded as a final verified due-diligence report.

Mark each item only after observing the actual interface. A passing GitHub CI
run does **not** substitute for this UI walkthrough.

## Feedback to return

Record the scenario, last button clicked, expected outcome and what appeared.
Include the exact error text if safe to share. Do not include API keys or private
company documents. The useful question is whether the decision, supporting
source and remaining review work are understandable without reading the code.

## Verified CI checkpoint

Commit `a1d6b99` passed all three GitHub Actions jobs in run #264:
unit tests, scripted offline integration, and network-blocked acceptance.
The network guard permits Unix-domain socketpair notifications used internally
by Python's event loop while rejecting IP socket traffic. This is a scripted
offline verification milestone, not evidence that autonomous paid-model
analysis has been validated.

## Honest portfolio description

Built a Python/Streamlit due-diligence prototype with PDF extraction, financial
arithmetic and source-evidence checks, human approval of financial submissions,
and tested pause/resume controls. Demonstrated approval, rejection, correction
recovery and request-limit stops through scripted offline SDK workflows.
Live autonomous reasoning and paid continuation validation are outstanding.
