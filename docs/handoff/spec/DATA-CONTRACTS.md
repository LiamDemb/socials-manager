# Data, identity, measurement and lineage contracts

## Core stored records

Use UUIDs internally. External IDs/handles are mappings, not primary keys. The reference SQL describes essential relationships/constraints and is verified to load; the development agent creates complete ORM models/migrations from this contract. No production schema is already deployed.

| Record | Required content/invariants |
| --- | --- |
| Instance configuration | Own artist ID, IANA timezone, defaults/schema version; exactly one configured artist, no tenant dimension |
| Artist/external identity | Aliases, canonical type, provider ID/URL, verification state/evidence/time and valid interval; active provider ID uniquely maps to one identity |
| Promoted object/relationships | Kind, name, artist, date precision/authority, official URLs/provider mappings; release-track membership verified, event timezone explicit |
| Campaign/resources | Type/window/anchor dates/object, audience, channels/accounts, assets-ready dates, budget minor units/currency, weekly labour and format caps, status/revision |
| Outcome version | Metric/version, entity/account/scope, gain/total/rate meaning, target, baseline references, period/window/zone/coverage and direction; immutable semantic change |
| CampaignOutcome/ActivityOutcome | Many-to-many IDs + primary/supporting role; no copied work or measurement |
| Activity | Campaign, purpose/type/channel/format, brief/checklist, planned UTC/local/zone or all-day date, actual execution, state, references/recommendation, revision |
| Execution event | Actor `local-owner`/system, prior/new state, actual time/URL/reason and recorded_at; correction/reopen retained |
| Source/policy/capability | Provider/account/route, purpose permissions, conditions/reference/effective dates, retention, metric availability/coverage/zone, secret reference only |
| Raw source/import | Exact bytes hash, safe relative path, original filename, parser/mapping version, source entity, collection/import time, preview/commit/undo states |
| Observation/version/contribution | Logical source key, metric/entity/window/dimensions, value or missing reason, unit, observed/available time, source row, revision and contributing imports |
| Interpretation version | Labels/entities/spans, rules/model/prompt/schema, review state, reviewer, recorded/available time; original text unchanged |
| Cohort/version/member | Inclusion dimensions/weights, eligible pool/exclusions/pins, member identity versions, purpose and selected_at |
| Finding/version | Inputs, metric/context/age, method, sample/missingness/confounders, result/support, uncertainty, cutoff and valid/stale state |
| Evidence bundle | Eligible input/version IDs, source-policy versions, transformations, scope/cutoff and content fingerprint; frozen snapshot |
| Recommendation/batch/decision | Bundle, tactics, concise reason/limits, support, assumptions, creative draft, scheduling decision, diff/base revisions, generation metadata, accept/reject/modify |
| Experiment/version | Hypothesis, variable, outcome version, activity links, comparison/pre-post/exposure windows, confounders, protocol approval and learning decision |
| Model/forecast run | Purpose/model/hash/version, eligible dataset/cutoff, parameters, validation report, frozen prediction/interval, evaluated outcome and status |
| Audit/job/outbox | Transactional decisions/mutations, idempotency keys, revision references and recomputation jobs |

## Temporal semantics

`event_time`: when publication/action occurred. `period_start/end`: what was measured, with half-open intervals. `observed_at`: when a provider measured or the value was collected, labelled accurately. `available_at`: when this system could use the particular value/version. `imported_at`: when the file entered the app. Unknown original measurement/export/availability timestamps remain unknown, not inferred from a row date.

Store timed instants in UTC plus the user's IANA zone and original provider offset. Preserve date-only provider grain separately. Spotify aggregate UTC days cannot be reconstructed into Perth local days. Display explicit source-day semantics. DST nonexistent/ambiguous local times must be resolved/validated before conversion; do not use a fixed `+08:00` implementation outside the prototype.

Backtests use input/interpretation/cohort versions available before the forecast cutoff. A current lifetime count on an old post cannot serve as its historic day-7 response. Retrospective exported data can be revised and cannot prove historic real-time availability; disclose that limit. Prospective ingestion creates an honest availability ledger.

## Metric algebra

| Metric | Scope/grain | Calculation |
| --- | --- | --- |
| Recording streams | One recording, daily flow | Sum eligible non-overlapping days; release totals use verified distinct recording membership |
| Artist streams | Artist daily flow | Sum separately; never add overlapping artist and recording series |
| Saves/playlist adds in supplied audience CSV | Artist daily flow | Sum within artist/window; not single-level saves or pre-saves |
| Daily listeners | Artist daily unique | Show daily values; sum is not period-unique listeners |
| Monthly listeners/active/super listeners | Rolling 28-day stocks/nested subsets | Latest compatible snapshot; neither sum snapshots nor nested segments |
| Followers | Platform/account stock | Latest/current minus compatible baseline for gain; missing baseline → Unknown |
| Confirmed pre-saves | Provider + identified release, declared snapshot/flow/unique definition | Follow provider contract; clicks, saves and playlist adds remain separate |
| Tickets | Event net paid/issued definition | Latest cumulative snapshot or explicitly incremental net flow; define refunds/cancellations and never mix transport types |
| Reach/views/interactions | Platform/media + metric/version/window/age | Comparable age and metric; repeated cumulative snapshots replace for current result, not sum |
| Ratios | Explicit numerator/denominator/window | Compute from compatible counts; denominator zero/unknown → undefined, not zero |
| Merch | Item net units/revenue/currency | Respect returns and granularity; no cross-currency addition |

Zero is an observed value. Missing/unsupported/delayed/stale/permission-denied are states, not zero. Period coverage includes required versus observed intervals, data-through date and partial-window status. Targets do not generate observations. Completion does not advance a goal.

Outcome baseline selection is explicit and source linked: latest eligible comparable stock at or before start, with disclosed maximum acceptable gap; if unavailable ask for a reviewed baseline or show Unknown. Target “+100” is a gain, not total 100. Shared outcome reports deduplicate by outcome version ID; campaign overlap is not causal attribution.

## Reviewed import protocol

1. Store/validate exact bytes and source mapping, with upload/encoding/size bounds. Guessing from a filename never establishes canonical identity.
2. Parse to staging using a pinned schema. Show metric scope, UTC dates, range, freshness, totals/latest values, invalid rows, new/equal/revised keys and unsupported fields.
3. Logical observation key includes provider/source scope, entity, metric definition/version, period/grain and returned dimensions. Equal values are no-op facts while contribution provenance may add a source import. Renaming a file cannot create another recording or duplicate counts.
4. Review conflicting values. Append an immutable correction revision/supersession with actor/reason, not overwrite raw history. Recheck preview/input/policy/mapping revisions immediately before atomic commit. Any invalid/stale/conflicting unapproved row blocks the selected batch.
5. Reconcile stored counts and source-shaped/common-format exports. Repeat commit is idempotent. Partial failure rolls back facts and cursor together. Undo removes only the batch's contribution; retain a fact independently supported by another import and recompute active revision selection.
6. Invalidate dependent findings/bundles/proposals and show changed/source freshness. Approved work is flagged, not silently rewritten.

The bundled investigation's conflict strategy rejects the whole attempted batch; production adds reviewable revision resolution. It does not prove concurrent upload security or production undo.

## Real supplied data

`data/real-inputs/README.md` and the bundled import metric contract are authoritative for the two actual formats. Both span 1 Jan 2024 to 28 Sep 2026: 2,004 source rows, 9,018 metrics, five non-zero streaming days (24–28 Sep). Recording and artist streams each total 200, not a combined 400. Artist saves total 25, playlist adds 15, latest followers 22, monthly listeners/active listeners 94 and super listeners 1. These are historic supplied values, not current account totals or calibrated training history.

The supplied artist URL yielded `3kL0Ts1i5vPiod2G2DxAu6`. The recording is still `provisional:better-man:01`; require explicit track URL/ISRC/date mapping for external joins. Earlier vision's approximate Instagram follower count and prototype's sample follower counts are not replacements for real current data.

## Corrections, deletion and exports

Interpretation corrections preserve originals and supersession; approvals pin evidence versions. Source deletion/use revocation invalidates every dependent transformation, bundle, cache, dataset and affected model/report. Purge retained content where required and retain only permitted minimal tombstone/audit metadata. An “append-only” principle never overrides a mandatory deletion rule.

Exports include metric/scope/window, source/time, revisions and coverage. Exclude secrets and any unpermitted private peer/personal content. A raw file/normalised export is not a permission grant for downstream model use. Import source policies are carried into derived data and model dataset manifests.
