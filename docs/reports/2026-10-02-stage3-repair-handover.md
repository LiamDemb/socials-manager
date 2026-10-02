# Stage 3 repair handover (2 Oct 2026)

> **Selection superseded:** Primary-outcome metric matching for tactic eligibility was removed by [ADR 0004](../adr/0004-planning-relevance-vs-evidence.md) and [planning amendment handover](2026-10-02-stage3-planning-amendment.md). Repair items below remain valid for bundles, scheduling, Ask, and policy.

## Commands

```sh
bin/socials-manager test
.venv/bin/python manage.py qualify_llm   # requires mlx-lm; fails on deterministic_fallback
.venv/bin/python manage.py llm_health
```

## Policy rollback

Do not delete `SourcePolicyVersion` history. To restrict a purpose, insert a new version with explicit assessment via admin or shell; `sync_source_policy` is no longer called from `ensure_spotify_source` / Instagram ensure.

## What changed

- Campaign/tactic/metric contracts (`intelligence/contracts.py`, `tactics-v2`)
- Scoped evidence bundles (`intelligence/evidence.py`)
- Synthesis with support labels, recommendation records, no wholesale LLM abort on primary metric
- Operational preview without unconditional gap line
- Shared `sources/eligibility.py`
- Ask retrieval (`intelligence/ask_retrieval.py`)
- MLX resident worker (`intelligence/llm_worker.py`)
- Adaptation accept applies diffs; experiment lifecycle API
- Dynamic Why/Strategy copy

## Smoke checklist

- [ ] Create single release with evidence checkbox; review shows tactics or specific gaps
- [ ] Approve campaign; Why shows support for evidence-backed rows
- [ ] Ask with a campaign-specific question
- [ ] `qualify_llm` with MLX installed reports `backend: mlx-lm`

## Stage 4

Numerical forecast validation remains not run.
