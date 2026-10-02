# Stage 3 requirement map (repair baseline)

**Status:** Stage 3 reopened for repair (2 Oct 2026).  
**Bar:** [acceptance-cases-stage3.json](acceptance-cases-stage3.json), [INTELLIGENCE.md](../handoff/spec/INTELLIGENCE.md).

| Requirement | Implementation | Verified |
| --- | --- | --- |
| AC21 Evidence-backed generation and abstention | `intelligence/synthesis.py`, `evidence.py`, `tactics.py`, `assessments.py`, `composition.py` | `tests/test_stage3_repair.py`, `tests/test_stage3_planning_amendment.py` |
| Planning relevance vs evidence (ADR 0004) | `needs.py`, `evidence_slices.py`, `candidate_tactics`, `compose-v1` | Amendment acceptance cases |
| AC22 Constrained scheduling | `intelligence/scheduler.py`, `SchedulingDecision` on create | Tests + activity Timing |
| AC23 Adaptation review | `adaptations.py`, API decide, apply on accept | Tests |
| AC24 Experiment lifecycle | `experiments_service.py`, Learning UI, API | Tests |
| AC32 LLM qualification | `llm_adapter.py`, `llm_worker.py`, `qualify_llm` | Must not pass on fallback |
| AC33 Grounded Ask | `ask_retrieval.py`, `ask_service.py`, shared `eligibility.py` | Tests |
| Operational checklist | `campaigns/services.py` `preview_operational` | Stage 1 regression |
| Policy per purpose | `sources/eligibility.py`, latest DB policy versions | Contract tests |
| Why / Strategy honesty | `why.html`, `campaign.html` strategy tab | Browser tests |

**Disconnected before repair:** tactic type/metric mismatch, artist-only bundles, static gaps, unwired experiments/adaptations, client-trusted provenance, policy sync on every boot.

**Stage 4 (out of scope):** numerical forecast gate AC25/AC34.
