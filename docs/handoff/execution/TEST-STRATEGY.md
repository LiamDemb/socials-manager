# Testing strategy and release evidence

## What to prove

Test the full loop: authorised/raw input → scoped observations → eligible findings → explainable proposal → human approval → dated execution → compatible measurement → reviewed learning. Data transport, UI usability, permitted model use and model validity are separate claims. Passing one does not prove another.

Tests run without live accounts by default against isolated temporary roots. Live probes are explicit, authorised, read-only/minimally necessary and tagged. Do not put production credentials or private data in public CI. Real CSV regression fixtures can run locally in a private environment; synthetic fixtures remain clearly labelled.

## Test layers

| Layer | Main checks | Evidence |
| --- | --- | --- |
| Pure rules | Metric algebra, scope, cutoff/eligibility, support, schedule/ranking, execution states and protocol transitions | Fast deterministic tests with frozen clock/versions |
| Database/service | Foreign keys/unique keys, revisions, idempotency, conflict rollback, undo contributions, atomic approvals, leases and invalidation | Real temporary SQLite file with independent connections/restart |
| Adapter contract | Parsed actual formats, mocked provider shapes, pagination/retries/partial fields, revoked token/schema changes | Sanitised fixtures and per-format capability matrix |
| Live integration | Actual account identity/fields/timezone, collection/pagination, refresh lifecycle and realistic source health | Dated route/API/account report; secrets redacted |
| Browser end-to-end | Creation/edit/approve/execute/measure, tabs/nested Back, long dialogs, errors/reload | Audited browser test runner, screenshots/geometry/focus assertions |
| Model evaluation | Grounded schema/context extraction and numerical forecast quality separately | Frozen permitted datasets, manifests, baselines, held-out results |
| Operations | Install/restart/wake/offline, migration, backup/restore, deletion and no secret leaks | Reproducible run report plus restored-data reconciliation |
| Owner acceptance | Creative usefulness, clarity, real source identity and practical workflow | Compact stage smoke checklist and recorded decision |

Use the framework's standard unit/service runner and an audited browser runner such as Playwright if provenance passes. Do not add a large testing dependency stack without review. Tool selection must not substitute for observable acceptance criteria.

## Real Spotify regression fixture

Run the bundled investigation against exact supplied files in a fresh output folder. Assert 2,004 source rows and 9,018 observations; dates 2024-01-01 through 2026-09-28; exact values survive source-shaped/common-format round trip; repeat/renamed imports create no duplicate facts; invalid counts/headers/dates reject; unapproved revisions roll back.

Specific totals: recording streams 200 and artist streams 200 separately; artist saves 25, playlist adds 15, latest followers 22; monthly listeners 94, active 94, super 1. Only five non-zero streaming days. Artist-versus-recording, daily-unique versus period-unique and flow-versus-snapshot mistakes are release-blocking. CSV zero padding is retained, not proof of useful model history.

Production adds cases the POC did not cover: upload size/encoding/path limits; preview stale mapping/policy; concurrent commits; explicit reviewed correction; two imports supporting one observation then undo; overlapping ranges; schema evolution; missing days/null versus zero; crash between raw-file staging and DB commit; replay after restart; exporting dangerous spreadsheet cell text safely.

## Recommendation and timing fixtures

Separate facts/interpretations/findings/creative drafts. Test no-evidence abstention, unresolved/excluded peers, wrong recording/event, stale/restricted source, fake citation, future-after-cutoff information, public/private metric mismatch, missing assets, no email list, channel not available, budget/capacity conflicts and duplicate intent.

Every accepted recommendation must resolve cited evidence/version IDs and target scope and pass deterministic constraints. Unsupported tactic generation must be rejected, not repaired with invented evidence. Operational setup is explicitly classified. Model/prompt injection cannot change policy, fetch secrets, write records or request tools.

Timing cases: common seven-day versus lifetime results; real publication rather than planned time; timezone unknown; hourly-only distribution cannot generate weekdays; unsupported format/account; sparse/confounded grouping; hard date; blackout; shared capacity; manual override; DST skipped/ambiguous times; new evidence leaves approved items fixed; stale draft cannot approve; moved test flags protocol. The synthetic eight-post v4 example verifies mechanics only.

## Execution and measurement

Frozen clock before/after 5 pm; today versus next day in artist timezone; overdue all-day after local day end; terminal state precedence; future completion rejected; skip/cancel reason; reopen history; completed drag blocked; paused campaign prompts suppressed; actual time distinct from planned.

Completion must not change followers/streams/tickets or confer success. Repeated cumulative snapshots replace for current value, never sum. Missing baseline/window coverage shows Unknown/Partial. Shared outcome reporting counts one contract once and does not attribute artist movement to one campaign. Counter/correction/refund semantics are tested under provider definitions.

## Live connector proof

For Meta, capture actual authorised identity, route/API/scopes, available own media/metrics, timestamp/offset, optional online-followers bucket shape/timezone, last success/coverage and a second collection. Test cursor/replay recovery and source-health error paths with fixtures where live failures would be unsafe to force. Unsupported is a valid result but not a supported metric pass.

For optional pre-save/ticket automation, compare actual report/API sample to a provider total for the identified release/event, verify revisions/duplicates/net semantics and record retrieval/use permissions. Do not mark planning-channel support as integration support. Spotify API cannot be a shortcut around source-use restrictions; the real required outcome path is CSV first.

No live Meta, model or automatic provider test has already passed in this handoff. Existing “connect” buttons are mockup interactions.

## Semantic/model readiness

Audit model/runner/build and weights/licence/hash before downloading/enabling. Start with permitted hand-labelled examples and rules baseline. Split by independent campaign/artist if enough data; otherwise disclose the smaller unit and avoid broad transfer claims. Freeze holdout and annotation policy; unknown/multilabel/contradiction cases are essential.

Evaluate parsing/schema, per-label/link precision/recall, abstention, evidence-span validity, invented entity/citation rate, latency/memory and recovery. Hard release requirements: accepted outputs have valid schema/real permitted citations, no accepted invented source/identity, no policy or mutation bypass. Set task-specific quality thresholds before opening holdout, justify them by impact and report denominators/uncertainty. A 30-caption smoke test is not a reliable production accuracy claim.

Grounded synthesis is tested for factual support, unsupported-tactic rejection, editable useful briefs, overlong text handling and evidence gaps. Owner reviews creative utility; this cannot be inferred from JSON validity. Local inference offline/failure falls back without data loss.

## Forecast evaluation early, release conditional

Stage 1 tests dataset manifests, as-of ledger, rolling splits, baseline calculations and prospective prediction capture on original synthetic fixtures. Permissions or five active real days can block fitting; record Blocked/Insufficient data accurately. Data collection/evaluation readiness continues.

When permitted and adequate, evaluate one scoped trajectory using recent-history/seasonal-naive baselines and a small statistical candidate. Freeze development origins/final interval, tune only on development, evaluate the final interval once and collect prospective forecasts before outcomes. Report MAE/appropriate count error, bias, coverage/width, sparse/regime cases and availability/revision limits. Never manufacture day-7 metrics or causal strategy lift from aggregate streams.

Predeclare useful improvement/coverage criteria and sample sufficiency, record them before final evaluation, and retain the report even on failure. Model parameters/dataset/hash/source policy and cutoff identify exactly what was fitted. “Training works” means a reproducible eligible fitting run and correct artifacts; “prediction is useful” additionally requires independent comparison/calibration evidence. Bayesian toy updates do not prove either for the real target.

## Browser/accessibility acceptance

Test actual production UI at 360×640, 768×1024, 1440×900, 812×375 landscape and 200% zoom/text enlargement. Long creative brief/rationale, long URL, many cards, short viewport, validation errors and expanded source detail must not overlap or hide actions.

Assert dialog scroll reachability, header/action access, keyboard body scroll, focus containment/return, Escape dismiss, Back navigation/restored drafts/scroll/focus, current-state refresh after mutation and no hidden duplicate modal. Evidence tablist/order/URLs remain constant through drill-down/back. Calendar has keyboard/date-list equivalent to drag. Status is understandable without colour, reduced motion works and generated/imported text is escaped.

Node VM checks are useful regressions for the reference source but cannot assert rendered geometry or assistive technology.

## Recovery/deletion/security

Use a real SQLite file: contention/timeouts, two stale approval/import requests, crash/restart lease recovery, raw orphan cleanup, disk-full safe failure and rollback. Runtime inventory verifies a patched SQLite before WAL or selects rollback journal.

Backup while app is active using a consistent snapshot; restore to a new root; reconcile rows/checksums/file references and run full smoke. Rehearse migration/rollback on a restored copy. Deleting/revoking a source invalidates dependent findings/datasets/cache/model outputs and cancels jobs; required purging wins over append-only history. Exports contain no credentials/unpermitted private information. Model prompts/logs also obey policy.

## Owner smoke reviews

| Review | Owner actions |
| --- | --- |
| Stage 1 | Import supplied files; inspect totals/scope/freshness; create campaign/outcome; complete an activity; verify completion did not fabricate progress; reopen after restart |
| Stage 2 | Inspect real source capability; finding → observation → source → Back; correct one label/peer identity; inspect matched reference and gaps |
| Stage 3 | Run release/growth/show creation; inspect Why?/Timing/brief; edit/approve; execute; accept/reject a change without surprise mutations |
| Stage 4 | Short viewport/keyboard use; restart/offline; import revision; backup/restore; read source/model capability limitations and approve concrete release |

Owner acceptance supplements automated tests; it cannot waive incorrect totals, source restrictions or falsified verification.

## Report format

Store stage report with commit/environment, tested acceptance IDs, fixture class, commands/results, failures/fixes, live source/model versions, owner decision and remaining gates. Status vocabulary: Passed, Failed, Not run, Blocked, Insufficient data. Include reproducibility commands and rollback. No empty green check for an unrun integration. Test selection grows only for changed behaviour/failures or unresolved concerns; avoid repeatedly running the same broad suite without reason.
