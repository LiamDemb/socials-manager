# Band Evidence: final development handoff

Prepared 1 October 2026 for an AI development agent. Product owner: Liam Demb. Initial artist: Opal Season.

**Ready to start final-product development. No further general prototype round is required.** This package is the authoritative build brief, with the current UI reference, working logic experiments, real import evidence and historical decisions together. It is not a finished application or a claim that live integrations or models have passed release tests.

## Start here

1. Read [AGENTS.md](AGENTS.md) and [spec/DECISIONS.md](spec/DECISIONS.md).
2. Read [spec/PRODUCT.md](spec/PRODUCT.md), [spec/USER-FLOWS.md](spec/USER-FLOWS.md) and [spec/UI-CONTRACT.md](spec/UI-CONTRACT.md). Open [the final interactive prototype](reference/current-prototype/prototype.html).
3. Read [architecture and storage](spec/ARCHITECTURE.md), [data contracts](spec/DATA-CONTRACTS.md), [integrations](spec/INTEGRATIONS.md), [intelligence](spec/INTELLIGENCE.md) and [operations](spec/OPERATIONS.md).
4. Execute [the four-stage development plan](execution/DEVELOPMENT-PLAN.md) using [backlog.json](execution/backlog.json), [acceptance cases](execution/acceptance-cases.json) and [the test strategy](execution/TEST-STRATEGY.md).
5. Begin Stage 1: persist the real Spotify CSVs, build reviewed import/reconciliation, and complete one campaign → activity → execution → observation → progress slice in SQLite. Prepare the early evaluation ledger in this stage; do not wait until the UI is complete.

Copyable agent instruction: **“Use START-HERE.md and AGENTS.md as the handoff. Execute Stage 1 in execution/backlog.json through its acceptance checks, fixing failures as you go. Do not ask for approval for each ticket. Return the working slice, test evidence, unresolved source capabilities and the compact Stage 1 owner review.”**

## Authority and boundaries

The root, `spec/`, `execution/` and `contracts/` describe the current target. A contract marked illustrative is an example, not an approved empirical threshold. `reference/current-prototype/` is the current interaction benchmark, with synthetic data and demonstration code. `reference/original-pocs/` and `reference/spotify-import/` prove only the checks described in their READMEs. `archive/` preserves history and original ZIPs; its former deployment, navigation, approval and task ordering instructions are superseded.

Latest explicit owner choices take precedence: **SQLite; one band installation; separate persistent dataset folder; no complex login, workspace system or cloud database.** Later reuse with a fresh database is documented, not part of this build. Historical PostgreSQL/AWS/owner-member workspace directions must not be carried into implementation.

Campaigns are the execution home. Goals are distinct reusable **Outcome** contracts underneath, linked to campaigns and activities. No separate strategy or duplicate calendar is created for a growth goal.

Spotify outcomes remain required. The supplied CSV path is technically proven and belongs in the first slice. Spotify-specific statistical fitting and LLM ingestion remain gated by source-use permission; five active streaming days do not validate forecasting. Do not silently turn this into a social-only product or call a synthetic evaluation real-data training.

## What is included

| Folder | Contents |
| --- | --- |
| `spec/` | Purpose, page responsibilities, user journeys, object/state/API/storage contracts, integrations, explainability, scheduling, operations and decisions |
| `execution/` | Four connected build stages, machine-readable dependency backlog, executable acceptance targets, agent checkpoint format and automated/owner testing strategy |
| `contracts/` | Recommendation JSON Schema and valid example, entity/relationship reference SQL, capability and support policy examples |
| `reference/current-prototype/` | Final v4 standalone HTML, original source/assets and 103-check Node VM suite |
| `reference/original-pocs/` | Five original dependency-free logic POCs and 14 logic + 12 rendering checks |
| `reference/spotify-import/` | Real Python/SQLite CSV importer investigation, 17-check test run, metric contract, database and round-trip evidence |
| `data/real-inputs/` | Exact supplied artist/recording CSVs with filenames normalised; private project data, never demo/training data by default |
| `research/` | Primary-source URLs, review dates, capability limits and provenance; full-page access distinguished from indexed/historical research |
| `archive/` | Original vision, review decisions, old calendar, earlier specifications/backlogs and six original ZIP packages |
| `tools/`, `verification/` | Reproducible package/POC checks and the actual final consolidation verification report |

## Reproduce this handoff's checks

Requires Python 3.11+ and a current Node.js runtime, already available in the consolidation environment. No package install or network connection is needed for these reference checks.

```bash
python3 tools/verify_package.py
python3 tools/run_reference_checks.py
```

These check the packaged material, not the future production app. The prototype suite uses a mock DOM in Node; browser layout, keyboard, assistive technology and live account tests remain production acceptance work. See [verification/CONSOLIDATION.md](verification/CONSOLIDATION.md) for exact run results and limits.

## Specific implementation gates

No unresolved product concept blocks Stage 1. Resolve canonical Better Man identity/date during setup, verify live Meta capabilities in Stage 2, audit any new dependency/model before use, and establish source-specific processing rights before enabling restricted operations. Pre-save/ticket automation depends on an actual provider, while reviewed reports/manual observations remain supported. A local semantic model must pass its benchmark; a numerical forecast must pass separate permission, history and validation gates. Finish independent work while a gate is pending; report its impact explicitly.

The final release must be an honest operational tool with real evidence, not the demo populated with fictional peers and apparent integrations.
