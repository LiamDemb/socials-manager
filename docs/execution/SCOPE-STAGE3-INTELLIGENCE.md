# Stage 3 scope overlay (authoritative for build)

Supersedes deferred "local model TBD" gates in PROJECT-CONTEXT for synthesis, Ask and evidence-backed campaign drafts.

## Planning amendment (2 Oct 2026, ADR 0004)

Tactic selection uses strategic roles, needs (`needs-v1`), dual assessments, and composition (`compose-v1`). Primary-outcome metric matching is **not** a selection gate. Evidence-backed labels require strict metric-scoped refs. See `acceptance-cases-stage3-planning-amendment.json`.

## Tasks

| ID | Deliverable |
| --- | --- |
| S3-01 | Tactic catalogue v3, evidence bundles, planning hypotheses, composition |
| S3-02 | `SchedulingDecision`, feasible windows, disclosed fallbacks |
| S3-03 | Campaign preview with evidence-backed activities; atomic create unchanged |
| S3-04 | `intelligence` app, MLX Llama 3.2 3B adapter, ADR 0003, `qualify_llm` |
| S3-05 | Experiments and adaptation proposals with accept/reject |
| S3-06 | Ask page and `/api/ask` |

## Acceptance mapping

AC21, AC22, AC23, AC24, AC32, AC33 — see `acceptance-cases-stage3.json`.

## Ask read path (owner decision, 2 Oct 2026)

Ask uses [`intelligence/ask_context.py`](../intelligence/ask_context.py) to load a **read-only** snapshot of stored records (Instagram capability, observations on any entity including recordings, catalogue, campaigns, findings, peers, inspiration). This is **separate** from `llm_ingest` on sources: campaign synthesis still honours `metric_allows_llm()` and denied Spotify/Instagram `llm_ingest` policies.

## Policy (owner decision, repair Oct 2026)

Latest stored `SourcePolicyVersion` rows may allow all purposes on this loopback instance. New sources receive an initial policy only when none exists; `ensure_*` does not auto-upgrade on boot. Eligibility is per-purpose via `sources/eligibility.py`.

## Blocked (unchanged)

- Stage 4 browser matrix and forecast gate (AC25, AC34)
