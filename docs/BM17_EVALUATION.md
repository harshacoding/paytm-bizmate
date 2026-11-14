# BM-17 integration and policy regression

BM-17 backend evaluation is implemented on the same `codex/bm-14-15-campaign-handoff` branch as BM-14/15. This evaluates synthetic API, persistence, workflow and policy behavior alongside the integrated BM-09/16 interface. Full BM-17 acceptance still needs the pending UI and BM-12 checks below.

## Repeatable evaluation

From the repository root, with the existing dependencies installed:

```sh
# Backend evaluation with JSON, JUnit and console-log artifacts
npm run evaluate:policy

# Optional new output directory. Existing evidence is never overwritten.
npm run evaluate:policy -- --output-dir .local-artifacts/bm17/my-run

# Full project checks, including the same backend evaluation and current frontend checks
npm run check

# Only the new cross-workflow matrix
uv run --project backend pytest backend/tests/test_policy_regression.py -q
```

A running API or model API key is unnecessary. Tests use temporary SQLite databases and an offline demo planner. Explicit model-adapter tests use mocked HTTP responses. The evaluation command clears inherited pytest filtering options so the complete backend suite runs.

The default artifact directory is `.local-artifacts/bm17/<UTC timestamp>/`. It contains:

- `report.json`: observed results, suite counts, policy-matrix count, skip reasons, failures, exact command, Python version, Git revision, working-tree state, source/dependency fingerprints and outstanding acceptance work.
- `junit.xml`: individual test outcomes.
- `pytest.log`: captured console output.

The command exits nonzero for failed, empty, malformed or incomplete evidence and for skipped policy-matrix cases. A failed run reports violation metrics as unknown rather than claiming zero. A passing report records zero observed approval bypasses and false completions within the executed synthetic assertions. These observations are limited to the test suite. Commercial outcomes and live-provider performance are unmeasured.

`npm run check` invokes the evaluator once, then runs the existing frontend tests, type checking, build and contract check. The existing GitHub Actions workflow runs this evaluation through `npm run check` and includes its results in the job logs. Automatic artifact upload is deferred because the current Git credential lacks workflow-update permission. Local JSON/JUnit evidence remains available. Existing `npm run test:api` remains available for ordinary pytest use.

## Observed local evaluation

The full `npm run check` run on 2026-11-14 passed:

| Check | Observed result |
| --- | --- |
| Backend suite | 471 passed, 0 failed, 1 skipped |
| New cross-workflow policy matrix | 31 passed |
| Report-integrity regressions | 7 passed |
| Approval bypasses observed in executed assertions | 0 |
| False completions observed in executed assertions | 0 |
| Existing frontend tests | 6 passed |
| Lint, typecheck, production build and contract drift | Passed |

The existing skip is `test_sqlite_restart_preserves_approval_receipt_and_verification[memory]`, because an in-memory adapter cannot exercise disk restart. SQLite and separate-process restart cases run and pass.

Local raw evidence is saved under `.local-artifacts/bm17/20261114T084603.531488Z/`. The report identifies the base Git revision, dirty working-tree state at execution and exact backend source/dependency fingerprints. The evidence directory is intentionally excluded from Git; subsequent local evaluations create fresh evidence directories, and CI prints evaluation results in its job logs.

## Coverage and acceptance mapping

| Requirement | Executed evidence |
| --- | --- |
| Equivalent requests across languages | `test_policy_regression.py` compares full action arguments for settlement, campaign and handoff across English, Telugu, Hindi and mixed requests. Frontend language preferences deliberately differ from actual input language. |
| Language switch and history after restart | A Telugu conversation retains original text and detection/response metadata. An associated campaign switches to English without changing the approval, then completes after app restart. Separate-process recovery tests remain part of the full suite. |
| No approval or instruction-based authority | Multilingual merchant text, forged identity headers and explicit “complete” instructions leave approvals pending and the provider ledger empty. |
| Exact approved inputs | Modified messages/summaries, recipient sets, costs and task IDs cannot execute for any of the three workflows. BM-14 edit tests require a new approval snapshot. |
| Merchant isolation | Another merchant cannot use known task, approval, receipt or checkpoint identities, or mutate the original merchant's records. |
| Exact reconciliation and unknown evidence | BM-10 tests and workflow tests assert 1,856,680 paise expected and 16,680 paise gap. Missing/conflicting inputs retain unknown amounts and cannot falsely complete. |
| Consent and inactivity boundary | Segmentation tests cover the exact 30-day boundary, unknown/future histories and missing consent. BM-14 tests cover revoked consent, recent orders, newly eligible customers and transactional send races. |
| Cancellation and review | BM-06 and BM-14/15 tests verify cancelled actions do not execute and changed inputs require review. |
| Read retry and fallback | Scripted report timeouts recover through bounded retries/source fallback or escalate with persisted attempts and errors. |
| Uncertain writes and replay | Real separate processes exit immediately after ticket/campaign provider commit. Resume recovers the existing action and never duplicates it. Edited campaigns and handoffs also survive timeout/restart. |
| Independent verification | Failed read, false delivery counts, wrong reference/task/merchant and missing/wrong support route cannot yield completion or verified routing. |
| Persisted ledger invariants | BM-17 compares actual provider rows against exact approved inputs and durable receipts, including merchant, provider reference and idempotency key. Completed tasks require independent successful reads. |
| Stale settlement information | The original credit report and merchant claims of repayment cannot close a verified-ticket task. Its saved proof remains unchanged and status remains `WAITING_EXTERNAL`. |
| Unsupported bank-account change | Only an approved support ticket can be created, with minimal information and an independently verified route. The bank change remains pending with human support. Permission gaps cannot grant a workaround. |
| Honest reporting | Reporter regressions reject failed/empty/invalid evidence, interrupted runs and skipped policy-matrix cases. Existing backend skips remain visible. |

## Pending acceptance

- **BM-09/BM-16 UI:** BM-09/BM-16 is now integrated from main. Final combined-branch browser review remains pending, including BM-14 managed campaign editing controls and user comprehension. Existing frontend tests are included in project checks, but do not establish acceptance of these future flows.
- **BM-12 scheduled settlement closure:** The scheduler is currently a feature-pending stub. Due-task execution and closure only on fresh matching credit evidence cannot be signed off yet. Current tests prove that stale reports and user claims do not close the open task.
- **Live model/provider evaluation:** Optional structured model extraction has mocked transport tests. Paid live-model calls and production integrations are outside this offline synthetic evaluation.
- **Reviewer sign-off:** Harsha's final integrated acceptance remains pending. BM-17 is not marked fully complete in the backlog.

## Integration with latest main

Integrated main `960c108` (BM-09/BM-16 merchant workspace, evidence UI and multilingual voice demo) into the BM-14/15/17 branch without Git conflicts. The merged branch passes 487 backend tests with one expected in-memory/disk-only skip, 74 frontend tests, Ruff, type checking, production build and API contract drift checks.

The existing merchant UI and voice implementation are preserved. Managed-task approval/resume still uses the backend orchestrator. BM-14 editable campaign review remains available through its typed API; the current UI leaves managed campaigns read-only before approval, so connecting that edit control remains an explicit UI integration item. BM-15 gaps, approvals, receipts and human-support pending status use the existing task views. This merge does not sign off new browser acceptance journeys or BM-12 fresh-credit closure.

The optional CI artifact-upload change is preserved locally on `codex/bm-14-15-17-with-ci-artifacts-backup`. The published branch retains main's workflow file and runs all checks through the updated package command.
