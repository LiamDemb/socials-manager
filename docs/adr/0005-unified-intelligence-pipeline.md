# ADR 0005: Unified intelligence pipeline (proposal v2)

**Status:** Accepted (3 Oct 2026)  
**Builds on:** ADR 0004 (planning relevance vs evidence compatibility)

## Decision

One shared pipeline: **agenda → AnalysisResolver → DecisionContext → compose-v1 baseline → bounded LLM narration**. Statistical runners (`post_response`, `interval_response`, `temporal_window`) are executable adapters with separate qualification. `blocked` (dependency/hardware) is distinct from `insufficient_data` (sparse valid samples).

## Components

| Module | Role |
| --- | --- |
| `intelligence/agenda.py` | Role-based analysis agenda |
| `intelligence/analysis.py` | Resolver, cache, queue |
| `intelligence/lineage.py` | Cache keys, invalidation |
| `intelligence/decision_context.py` | Frozen planner/Ask input |
| `intelligence/claims.py` | Claim kind validation |
| `intelligence/stats/*` | Family runners |
| `context/services.py` | Peer media pagination and coverage |

## Non-goals

Vector DB, AutoML, vision models, Stage 4 forecasts, per-channel causal attribution.
