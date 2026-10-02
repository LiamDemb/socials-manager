# Band Evidence: project context

Orientation for anyone working in this repository. It summarises; it does not replace the specification. When this file and `docs/handoff/` disagree, `docs/handoff/` wins, and within it `spec/DECISIONS.md` resolves conflicts.

## What we are building

An internal, single-artist tool (initial artist: Opal Season, owner: Liam Demb) that helps decide what to do next from collected data, and then records whether it worked. The loop:

data → observation → finding → recommendation → approved campaign → dated execution → compatible measurement → reviewed learning

The user decides at every step. The app drafts and records work; it never publishes, sends messages or changes the calendar without review.

## Authority

| Read for | Location |
| --- | --- |
| Assignment, binding constraints, dependency exclusions | `docs/handoff/START-HERE.md`, `docs/handoff/AGENTS.md` |
| Settled decisions and material gates | `docs/handoff/spec/DECISIONS.md` |
| Product, journeys, UI contract | `docs/handoff/spec/PRODUCT.md`, `USER-FLOWS.md`, `UI-CONTRACT.md` |
| Architecture, data, integrations, intelligence, operations | `docs/handoff/spec/ARCHITECTURE.md`, `DATA-CONTRACTS.md`, `INTEGRATIONS.md`, `INTELLIGENCE.md`, `OPERATIONS.md` |
| Stages, tasks, acceptance, testing | `docs/handoff/execution/` |
| Schema/proposal/policy contracts | `docs/handoff/contracts/` (reference, not migrations; examples are illustrative) |
| Live progress checkpoint | `execution/AGENT-STATE.json` |
| Engineering decisions made during build | `docs/adr/` |

The private handoff root (`handoff/`, Git-ignored) additionally holds the v4 prototype, original POCs, the real Spotify import investigation, the real CSVs and the archive. Those prove only what their READMEs state. `archive/` is history, never instructions.

## Settled, do not reopen

- One artist installation, one SQLite file and one persistent data root outside the repository (D01, D03). No tenancy, workspaces, app accounts or cloud database (D02). Loopback only. Second-instance provisioning is deferred and documentation-only.
- Campaigns are the execution home; outcomes are reusable, versioned measurement contracts linked to campaigns and activities, counted once (D04, D05).
- Evidence-backed, explainable proposals with human approval; no silent calendar changes (D12, PRODUCT adaptation).
- Observations, interpretations, findings, recommendations and creative suggestions stay distinct (INTELLIGENCE "Five different things").
- Spotify outcomes are required via reviewed CSV import (D07, D08). Spotify model-use permission and forecast validity are separate, independent gates (D10).
- No Chinese-owned or operated code, services, libraries or models; unknown provenance is blocked (D11, AGENTS.md).
- Final v4 prototype is the interaction reference (D06); its implementation shortcuts are not production architecture.
- Build default: Python/Django modular monolith, server-rendered templates, original browser JS modules, one leased SQLite-backed worker (D17, D18). Exact versions are audited in S1-01.

## Core model in one paragraph

An **Artist** (own, or reviewed peer) has **Promoted objects** (recording, release, event, video, merch) that may be pending before external identity is verified. A **Campaign** (Draft → Active ⇄ Paused → Completed/Cancelled) targets an object or, for growth, none; it links one primary and optional supporting **Outcome versions** through `CampaignOutcome`. **Activities** belong to one campaign, persist as Planned/Completed/Skipped/Cancelled, and derive Unscheduled/Upcoming/Due today/Overdue from server time and the IANA zone. **Execution events** record actual time, URL or reason and never advance an outcome. **Sources** carry per-purpose policies and capabilities; **import batches** stage, commit and undo **observation versions** with contributions and provenance. Outcome progress comes only from compatible observations, with Unknown/Partial where coverage or baseline is missing. Later stages add interpretations, cohorts, evidence bundles, findings, recommendations (Draft → Validated → Accepted/Rejected/Superseded), scheduling decisions, experiments and learning records. See `PRODUCT.md` and `DATA-CONTRACTS.md` for the full contracts.

## Open gates (block only the dependent capability)

| Gate | Current state | Blocks |
| --- | --- | --- |
| Better Man canonical identity/date | Provisional `provisional:better-man:01`; artist ID `3kL0Ts1i5vPiod2G2DxAu6` from owner URL | Durable external matching and release-relative analysis |
| Spotify numerical/LLM processing rights | Unresolved | Fitting, backtesting, inference and LLM use of Spotify-derived data |
| Forecast history | Five non-zero streaming days | Any validated forecast claim |
| Meta capabilities | Not probed | Automatic Instagram metrics and timing (Stage 2) |
| Pre-save/ticket provider | None selected | Automatic retrieval; manual/reviewed reports still work |
| Local model | None selected or audited | Semantic/synthesis automation (Stage 3) |

## Repository and data layout

| Path | Contents | Versioned |
| --- | --- | --- |
| `docs/handoff/` | Byte-identical normative copy | Yes |
| `docs/PROJECT-CONTEXT.md`, `docs/adr/`, `docs/reports/` | Context, decisions, stage and verification reports | Yes |
| `execution/AGENT-STATE.json` | Resumable checkpoint | Yes |
| application source, migrations, tests | Created in S1-01 | Yes |
| `handoff/` | Private full handoff, read-only | No (ignored) |
| Owner `DATA_ROOT` | `app.sqlite3`, `instance.json`, `imports/`, `assets/`, `backups/` etc. Default proposal: `~/Library/Application Support/BandEvidence/` | No, outside repo |
| Test/synthetic roots | Temporary directories per run | No |
| Real CSV regression fixtures | Read in place from `handoff/data/real-inputs/` via an explicit path setting; never copied into the repo or seeded | No |

## Environment (recorded 2 Oct 2026)

macOS 15.7.4 on arm64. Python 3.14.4 (Homebrew) linking SQLite 3.53.0, which is at or above the documented WAL-reset fix (3.51.3). The system `sqlite3` CLI is 3.43.2, below the fix: do not use it against a live WAL database. Node v23.10.0 is a non-LTS release, used only for reference suites; choose an audited LTS runtime if a browser test runner needs Node. No production dependencies are installed yet.

## Working rules worth repeating

No fictional metrics in the owner database. Completion never increments progress. Unknown is not zero. Every mutation is revision-checked and idempotent. Imported captions are untrusted text. Australian English, concise labels, no em dashes in product copy. Report checks as Passed / Failed / Not run / Blocked / Insufficient data.
