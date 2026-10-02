# Application architecture and data storage

## Small, durable application

Use one modular application on one trusted machine: browser UI → local application server → SQLite and persistent files. A separate local worker executes database jobs and optional model inference. No database server, cloud database, tenant platform, broker or vector service is needed.

Reference implementation default: Python/Django, SQLite, server-rendered HTML with original browser JS modules for calendar/forms/dialogs, original CSS and audited production server. This retains the earlier Python monolith direction while replacing PostgreSQL and app-account roles. Pin a supported stable release after ownership/licence/security review; a documentation `stable` redirect is not a version lock. The future dependency inventory is a build deliverable, not preapproved here.

The app serves assets locally, binds to `127.0.0.1` by default and uses the operating system's trusted access boundary. No workspace/user switcher or product account system. Same-origin/CSRF, allowed-host checks, upload limits and safe rendering are still necessary for a local web app. Connector OAuth authenticates the band to a provider, not a new app login. If remote/team access is later wanted, record an explicit new access-boundary decision before exposing the service.

## Code versus instance data

| Location under configured `DATA_ROOT` | Purpose |
| --- | --- |
| `app.sqlite3` | Relational source of truth: catalogue, campaigns/outcomes, activities, source lineage, observations, versions, proposals, jobs, decisions and audit |
| `instance.json` | One artist/instance identifier, IANA timezone and local defaults; no secrets; schema version |
| `imports/` | Exact user-supplied files and permitted raw provider payloads, hashed/content addressed with source-use metadata in DB |
| `assets/` | Band-owned/explicitly permitted assets linked by IDs/checksums, not huge DB blobs |
| `datasets/` | Reproducible eligible snapshots and labelled evaluation sets with IDs/cutoff/permission manifest |
| `models/` | Audited optional model artifacts or references, hashes/licences and approved numerical model versions |
| `reports/` | Backtests, integration checks and supportable learning reports |
| `cache/` | Regenerable retrieval/aggregates; never authoritative or included as new observations |
| `backups/` | Local backup destination by default; also copy approved backups off the same disk |

Source code/migrations/tests live in the repository; owner data and connector secrets do not. The data root must survive upgrades and restarts and must not be an ephemeral deployment folder. Seed metric/channel definitions and migrations into an empty DB; do not seed fictional peers/outcomes. Real import fixtures in this handoff are private evaluation inputs, not shipped demo data.

Use DB references to relative file paths, content hashes and source policy/version. Reject traversal/symlink escapes. A file is made durable before the DB transaction references it; temporary staging and interrupted orphan cleanup are explicit. Immutable content-addressed raw files make later backups and provenance reproducible.

## Modules

| Module | Responsibility |
| --- | --- |
| Catalogue | Artist/peer identity, external mappings, recordings/releases/events/items and date authority |
| Sources/ingestion | Purpose policies, capability probes, OAuth secrets references, raw files, preview/commit/revision/undo, collection jobs |
| Campaigns | Outcomes, resources, activities, dates, approvals, execution and audit |
| Context | Rules/local semantic extraction, reviewed labels/entity links, cohort inclusion and interpretation versions |
| Evidence | Compatible queries, robust summaries, findings, evidence bundles and invalidation |
| Planning | Candidate tactics, constrained scheduling, support rubric, proposed changes and validation |
| Learning | Experiment protocols/results, outcome evaluation, prospective forecasts and independent validation |
| Assistant | Replaceable bounded local synthesis/context extraction and grounded Ask |
| Operations | Backup/restore, source health, diagnostics, migration/recovery and dependency inventory |

Modules share a database through services, not by bypassing invariants. All evidence and model reads enforce source purpose, scope and as-of eligibility. No raw imported text gets tool access. Keep a small explicit API; do not split these modules into network services.

## SQLite rules

Enable foreign keys on every connection. Keep write transactions short, bound busy timeouts/retries, use conditional revision updates and idempotency keys. One worker with leases avoids overlapping scheduled work; it must not hold a write lock during network calls or inference. Parsing/analytics happen outside a write transaction, then commit checked results atomically.

WAL can support local reads while writing, but all database processes/files stay on the same host and local filesystem. Do not open the live DB from Dropbox/Drive/NFS or multiple computers. Before enabling WAL, verify the actual linked SQLite runtime includes the documented WAL-reset fix: 3.51.3 or later, or a verified fixed backport such as 3.44.6/3.50.7. Record the runtime, not only the Python version. If not available, use rollback journal until patched. See primary SQLite references in research/SOURCES.json.

Django/SQLite does not supply PostgreSQL row locks. Use `UPDATE ... WHERE revision = expected` / unique constraints and check row counts in a transaction. `select_for_update` must not be assumed to solve approval races. Test with a real file database and independent connections; memory-only tests miss locking behaviour.

Use real migrations and schema version checks. Outcomes/interpretations/metric definitions have immutable semantic versions; domain objects also have optimistic revisions. An audit event is not a second mutable copy of current state. Counts use integers; money is integer minor units + currency; ratios use explicit numerator/denominator. Do not rely on arbitrary JSON to enforce core relationships.

## Client/server state

Server owns durable entities, observations, policies, revisions, proposals, decisions and execution. Client owns route/tab/filter, form draft, selection, dialog parent route, expanded sections, scroll and focus. Typed dialog frames contain parent identity/route and UI state, not copied HTML/domain objects.

Writes have pending/success/error states. Double clicks/retries cannot duplicate actions. A stale draft/parent re-fetches current records and surfaces a conflict without overwriting unsaved fields. Close/Escape dismiss the flow; Back navigates one frame. Restart/reload restores committed data; optional temporary form drafts are not authoritative facts.

## Jobs and recomputation

Use a database job table with unique `(task, source/scope, scheduled slot or input fingerprint)`, due time, status, attempts, lease owner/expiry, safe error and cursor. Claim through a conditional transaction. Expired leases recover after restart. Backoff honours provider retry signals and has bounded attempts; dead jobs stay inspectable/retryable.

A domain transaction appends an outbox/invalidation event. The worker handles it idempotently: refresh eligible findings → compute candidate proposals if useful → deduplicate/cool down → make reviewable draft. No event applies a calendar edit automatically. Deletion/revocation cancels queued work and invalidates downstream data, including cached/model artifacts where required.

Recommended triggers: observation revision/maturation, execution completion/missed deadline, outcome baseline/window change, context correction, identity exclusion, source status or campaign/resource/key-date changes. Immutable bundles make it possible to explain an old decision while clearly marking it stale now.

## API/action contract

Names are target contracts to implement, not existing POC endpoints. Use local same-origin session/CSRF protection without app accounts. `expected_revision`, input size limits, enum/schema validation and `Idempotency-Key` apply to mutations. Common response envelope: `{data, revision, warnings}`; errors include stable `code`, field issues, safe message and retryability.

| Action | Important input/result |
| --- | --- |
| `POST /imports/preview` | File/source, explicit artist/object mapping → staged batch, metrics/range, new/unchanged/conflicting/invalid rows; no observations committed |
| `POST /imports/{id}/commit` | Preview revision + reviewed conflicts → atomic facts/revisions; reject changed mapping/source policy/input |
| `POST /imports/{id}/undo` | Reason/revision → invalidate only that batch's contributions; retain independently supported equal facts |
| `GET /sources/{id}/capabilities` | Per-metric route/API/purpose, coverage, timezone, freshness, last failure |
| `POST /campaigns` / `PATCH /campaigns/{id}` | Catalogue/outcomes/resources/window; versioned conflict checks |
| `POST /campaigns/{id}/draft` | Brief revision + eligible bundle → draft batch or gaps; asynchronous job if necessary |
| `POST /proposal-batches/{id}/validate` | User edits + current records → accepted constraints or blocked/stale reasons |
| `POST /proposal-batches/{id}/accept` | Selected diff/revision/idempotency → atomic activity/outcome/decision changes |
| `POST /recommendations/{id}/reject` | Reason/preference → decision + dedup fingerprint, no outcome result |
| `PATCH /activities/{id}/schedule` | New time/zone + revision → audit, rationale/protocol flag, capacity validation |
| `POST /activities/{id}/execute` / `reopen` | State, actual timestamp, URL/reason → event; no invented metrics |
| `POST /outcomes` / link actions | Versioned measurement contract, scope validation and no copies |
| `GET /evidence?tab=...&scope=...&as_of=...` | Fixed tab taxonomy, eligible facts/findings with versions/coverage |
| `POST /interpretations/{id}/review` | Labels/links/spans or unknown → new reviewed version and invalidation |
| `POST /peers/{id}/review` | Identity evidence/inclusion → cohort revision, dependent proposals stale |
| `POST /experiments` / approve/start/review | Frozen protocol and explicit allowed transition; immature result remains waiting |
| `POST /ask` | Context + question → permitted sources, answer/navigation or uncommitted proposal |
| `POST /backup` / local restore command | Snapshot/report, guarded restore path with integrity/version checks |

Every source/URL fetch uses approved provider adapters, bounded redirects and destination validation. A reference URL is not permission for arbitrary server fetching/private-network access.

## Second band later

Deploy the same release and migrations with a new instance ID, empty local SQLite file, empty data folders, new artist configuration and separate connector secrets. Populate definitions, then explicitly import that band's authorised data. Never copy the old band's observations, learned coefficients, goals, reviews, cache or evaluated datasets by default. Shared code/metric definitions are reusable; band learning is instance data.

Future command shape may be `make init-instance DATA_ROOT=/new/path`, followed by source setup and imports. This is documentation only: no instance manager or additional workspace feature belongs in the current backlog. One configured root is active per app process.
