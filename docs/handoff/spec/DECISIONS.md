# Decision ledger and readiness

This ledger is authoritative over the archived versions. “Accepted” means explicit owner direction or later instruction to proceed on the refined product. “Build default” is a bounded engineering choice that the agent can adjust through an ADR without another product prototype round.

| ID | Current decision | Status and effect |
| --- | --- | --- |
| D01 | One internal artist installation, SQLite + external dataset folder | Accepted latest storage discussion. Supersedes PostgreSQL/AWS database and multi-owner workspace assumptions. |
| D02 | App has no complex login or workspace system | Accepted. Loopback local service by default, OS access boundary, same-origin write protection. External source OAuth remains necessary. |
| D03 | Same application can later start with empty DB/data root | Accepted direction, provisioning automation deferred. Document clean-instance procedure; do not implement multiple active instances/UI. |
| D04 | Campaign-first UX with reusable distinct outcomes | Accepted progression into final development. Growth creates a time-bounded campaign; artist-wide outcome report deduplicates shared contracts. |
| D05 | Today is artist overview, Campaigns owns work | Accepted. Replaces old Today → selected goal → one experiment layout. |
| D06 | Final v4 is current UI reference | Accepted direction. Prior visual benchmarks and “UI unapproved/one-screen prototype next” instructions are historical. Production browser acceptance is still required. |
| D07 | Spotify outcomes are core | Binding original D1. Real CSV path now proven; do not substitute social-only scope. Model-use rights are a separate unresolved gate. |
| D08 | Reviewed CSV ingestion | Binding original D4, resolved from original handoff's interpretation. Preview, identity, duplicates and revisions before atomic commit. |
| D09 | Semantic suggestions with human review | Binding original D5. AI can interpret caption context from permitted data, not only polish copy. Rules and manual review remain functional. |
| D10 | Forecast evaluation early; release conditional | Binding original D6. Evaluation ledger/baselines begin in Stage 1; no trained/validated forecast claim from five active days. |
| D11 | No Chinese-owned/operated dependencies or services | Binding earlier constraint, unchanged. TikTok remains excluded despite generic platform suggestions in feedback. |
| D12 | Evidence → finding → reasoned proposal; user decides | Binding core purpose. Creative draft is not evidence. No unsupported prediction, invented citation or silent adaptation. |
| D13 | Dates/time are first-class and explainable | Accepted. UTC + IANA timezone, actual execution separate, common-age timing evidence and explicit availability fallback. |
| D14 | Experiments retained inside campaign learning/timeline | Accepted clarification. Optional protocol over real activities, not a parallel task system or prerequisite for every post. |
| D15 | Review Labels becomes Evidence → Review context | Accepted clarification. Exception queue, fixed evidence tabs, unknown state valid. |
| D16 | Publishing and outgoing communications are manual | Retained scope. Execution logging does not grant automated publication. |
| D17 | Python/Django modular monolith with templates/original JS | Build default based on earlier technical recommendation, updated to SQLite/no app accounts. Exact versions/dependencies must be audited; no stack is certified by this handoff. |
| D18 | One worker and SQLite-backed idempotent jobs | Build default. Avoid infrastructure until measured operational needs demand it. |
| D19 | Shared weekly labour + per-format limits | Build default replacing demo's substantial-post-only ceiling. One artist capacity budget, priority and manual overrides; no unlimited Stories/email. |
| D20 | Conservative qualitative evidence support | Build default. Versioned rubric; no LLM confidence or fabricated success probability. Tune only with recorded evaluation. |

## Goals/Plans rationale retained

| Model | Mental model/creation | Execution/reporting | Long-term cost |
| --- | --- | --- | --- |
| A: separate | Two entry points, goal needs an extra strategy step | Two progress views; standalone goals need action infrastructure | Duplicate lifecycles and calendars |
| B: distinct linked | Flexible enduring objectives | Shared work feasible, but more linking/ownership choices | Most relationship/navigation complexity |
| C: campaign-first | One brief, one strategy and calendar | Outcomes appear inside campaigns/Today/reports | Simplest workflow, but exclusive nesting would duplicate shared goals |

Use C in the UI with B's reusable measurement identity underneath. An outcome may link to several campaigns but its observations/progress are counted once. It is not exclusively owned by a campaign and linking it does not prove attribution. Revisit a separate Goals destination only if actual usage needs enduring goals operated outside campaigns. Do not add it speculatively.

## Material gates, not general discovery

| Gate | What resolves it | Blocks |
| --- | --- | --- |
| Spotify numerical/LLM processing rights | Applicable agreement/qualified source assessment or specific written clarification, recorded per intended use | Fitting/backtesting/inference on affected Spotify-derived inputs, not general campaign/CSV engineering |
| Better Man canonical mapping | Owner-supplied track URL or ISRC plus independently confirmed release date | Durable external recording matching and release-relative analysis; local pending object still works |
| Meta capabilities | Real authorised professional account test with pinned route/version, timestamps, metric fields, permissions and timezone semantics | Automatic metrics/timing for unsupported fields; imported/manual fallback remains |
| Pre-save/ticket provider | Actual scoped report contract/credentials and reconciliation fixture | That provider's automatic retrieval, not reviewed reports/manual observations |
| Model selection | Full ownership/runtime licence audit and benchmark on permitted held-out data | Automated semantic/creative features, not deterministic planning/execution |
| Forecast validity/history | Permitted longitudinal data, baselines, rolling evaluation, untouched holdout, prospective ledger | Validated forecast display, not descriptive results |
| UI/operations acceptance | Real browser/accessibility tests, backup/restore and restart/recovery drills | Release acceptance |

The owner is authorising final development now. Old F01–F06 discovery-only sequencing is superseded by the four-stage plan. No unresolved conceptual issue requires another general POC. Do not label the whole original Spotify feasibility gate passed merely because parsing passed.

## Deferred scope

Instance provisioning Makefile, multiple bands, remote/team access, broad hundreds-of-artists discovery, paid enrichment, full multi-stop tour optimisation, multimedia analysis, automated publishing, audience-level personal profiles, causal marketing mix modelling and strategic “album vs EP” career decisions. A tour-announcement campaign is supported; a full itinerary optimiser is not required.
