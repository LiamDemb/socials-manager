# Four-stage implementation plan for an AI agent

Execute continuously inside each stage. This is a dependency plan, not a calendar or fixed staffing plan. `backlog.json` specifies task dependencies, deliverables and acceptance IDs. `acceptance-cases.json` is the minimum behaviour matrix; add meaningful cases discovered during implementation.

## Working loop

Read current constraints → implement one coherent change → run relevant checks → fix failures → commit/update checkpoint → continue dependencies. Do not pause after every task or ask the owner to choose routine details. Each stage produces a runnable local version, reproducible report and one compact review. Actual credentials/permission decisions block only dependent capabilities; independent work continues. Never record an unavailable live/model test as done.

Before coding, create the development repository and initialise an execution checkpoint. Keep the full unpacked handoff outside versioned source: it contains private CSVs, derivative databases and nested original archives. Copy the current normative docs/plan/contracts to `docs/handoff/`; keep real inputs/import evidence in the separate ignored local data/fixture root. Do not commit the full handoff ZIP or its private archive subtree. Add data roots, secrets, backups and private fixtures to `.gitignore`. Record one small stack/SQLite/access ADR and dependency inventory. This setup is part of Stage 1, not another discovery milestone.

## Stage 1: durable real-data execution loop

**Deliverable:** a local working application using SQLite that imports the real supplied data, creates release/growth/show campaign contracts, approves manually authored/operational dated work, records execution and measures compatible outcomes.

Build catalogue/source/metric/outcome/campaign/activity records, revisions/audit/idempotency, local data root and backup. Implement the proven CSV formats with staged preview, explicit mapping, conflict review, atomic commit/undo, provenance and lossless download. Resolve Better Man mapping/date if supplied; otherwise preserve visible pending identity.

Build reusable responsive dialog/forms, fixed Evidence tabs and typed Back navigation early. Implement calendar/list, server time/IANA zones, planned-versus-actual execution and no-goal-increment-on-completion. Put genuine data-through/coverage in Today/Campaign Outcomes. No synthetic recommendation generator is required in this stage.

In the same stage, implement dataset/availability and prospective forecast ledger mechanics plus baseline/split evaluation on synthetic fixtures. Record the Spotify purpose gate and five-active-day limitation; real-data statistical fitting remains disabled while blocked. This preserves the owner's early forecast-validation priority without creating invalid model claims.

**Automated gate:** AC01–AC13, AC25, AC30, AC35 and relevant concurrency/recovery tests. Reconcile 2,004 source rows/9,018 metrics and exact source values; repeated import adds no duplicate facts. Restore the DB/files and repeat the core flow.

**Owner review 1:** import → inspect artist/recording scope → create one campaign/outcome → complete one activity → inspect unchanged versus observation-driven progress. Confirm actual source identity/date where needed and practical default capacity. The accepted UI/product model is not reopened.

## Stage 2: live sources and trustworthy evidence

**Deliverable:** own permitted source data, a useful curated peer/context workflow, reproducible findings and references with visible source health/capability.

Implement Meta route/capability probe, real own-account collection/refresh, leased jobs, timestamps/per-format metrics and optional availability support. Start a small manually curated verified cohort; permitted peer adapter only after its own probe. Add reviewed context/rules baseline, observation drill-down, source lineage, contextual/global inspiration and coarse timing findings using compatible data. Pre-save/ticket reports use explicit scoped contracts; do not claim unselected provider automation.

Collector work starts as soon as access is established, even while later screens are in progress. A blocked source gets an honest report/fallback; complete the functioning permitted route before claiming Stage 2's connector is passed.

**Automated gate:** AC14–AC20, AC26–AC29, AC31 plus earlier regressions. Live smoke produces a sanitised real capability report with account/route/API/time/metrics; mocks separately cover errors. Time buckets unresolved → fallback, not a guessed heatmap.

**Owner review 2:** source health/coverage → real finding → underlying observations → context correction → matched reference. Review actual peer relevance and source gaps together in one pass. If credentials are unavailable, present the completed independent slice and the exact unpassed live gate, not an apparent connected product.

## Stage 3: evidence-backed campaign creation and adaptation

**Deliverable:** three campaign scenarios generate editable structured proposals with traceable tactics/timing, concrete briefs, experiments and reviewed changes.

Implement evidence bundles, candidate catalogue/ranking, conservative support policy, operational fallback and deterministic scheduler across shared capacity. Use templates first; then audit/benchmark a local semantic/synthesis candidate and enable only passing permitted tasks. The optional inference adapter is replaceable and failure-tolerant. Build Why?/Timing/source layers, proposal validation/atomic approval and evidence revision invalidation.

Add experiment protocol lifecycle with real activities, mature measurement and inconclusive results. New performance/execution/constraint changes create deduplicated reviewed diffs. Grounded Ask uses the same purpose-limited retrieval and only proposes mutations. Keep automatic publication out of scope.

**Automated gate:** AC16–AC24, AC32–AC34 plus all affected regressions, held-out semantic benchmark if enabling a model, and no-policy-leak/evidence-citation tests. Unsupported evidence must cause abstention. Repeat generation inputs reproduce deterministic ranking/constraints; inference output need not be byte-identical.

**Owner review 3:** release in four weeks, +100 followers/month and show in six weeks. Inspect a practical brief, Why?/Timing/reference, edit/approve, execute, then accept/reject an adjustment. Confirm creative usefulness and honest gaps; record any model capability still gated.

## Stage 4: release qualification and validated learning

**Deliverable:** stable local release with complete operational instructions, verified recovery, realistic integration behaviour and honest model/evaluation reports.

Finish browser/accessibility matrix on all dialogs/screens, clock/DST/concurrency/restart cases, partial/stale/error states, deletion/invalidation, backup/restore and upgrade. Verify owner data stays separate from demo/test roots and inventory all release dependencies/model artifacts. Live connector acceptance is distinct from offline tests.

Run numerical forecast evaluation only on permitted adequate history with predeclared baselines/cutoffs/holdout criteria. If rights/history/quality are insufficient, ship an explicit Forecast unavailable state plus evaluation readiness report; do not manufacture a validated forecast or mark that feature's gate passed. Semantic automation similarly stays disabled if benchmark/provenance fails. The owner accepts the remaining capability limitations explicitly in release review rather than the agent quietly declaring them finished.

**Automated gate:** full acceptance matrix, environment/install smoke, migration/restore rehearsal and release checklist. No critical data invariant/UI accessibility failure. Reports distinguish Passed / Failed / Not run / Blocked / Insufficient data.

**Owner final review:** start the app fresh, inspect sources/import, create and execute a campaign, understand an evidence-backed suggestion, inspect measured progress and restore a backup. Review capability report and model-readiness report. Release approval is for this concrete build, not a broad architecture question.

## Stage deployment protocol

Build/test with temporary fixtures → restore owner-data copy → run migrations/integrity/smoke → backup active instance → upgrade same persistent root → smoke real data → retain previous release/snapshot for rollback. No destructive reset or environment replacement is allowed merely to make tests pass.

Changes to requirements, metrics/rubrics/thresholds/source capabilities are versioned. When one item is blocked, record blocker/evidence/dependent IDs and finish independent stage tasks. Resume from `AGENT-STATE.json`; do not restart or repeat accepted work after context loss. A stage can have an independent preview while a live gate is pending, but overall gate status remains honest.
