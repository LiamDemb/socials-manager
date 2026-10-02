# Stage 3 planning amendment handover (2 Oct 2026)

**Decision:** [ADR 0004](../adr/0004-planning-relevance-vs-evidence.md)  
**Supersedes for selection only:** primary-outcome `metric_mismatch` tactic gate from repair-era `tactics-v2`.

## Summary

- Removed metric overlap as a tactic **selection** requirement.
- Added `tactics-v3` catalogue (roles, contribution hypotheses, observable metrics).
- Added `needs-v1`, dual assessments, per-metric evidence slices, `compose-v1` set assembly.
- `synthesis-v3` proposes planning hypotheses without fake `evidence_backed` labels.
- UI: planning notes on preview, role/basis on cards, Strategy composition summary, Why progressive fields.
- Ask: `planning_decision` facts from `RecommendationRecord.payload.meta`.

## Migration notes

- Existing activities keep legacy `provenance.support` fields; new creates pin `strategic_fit`, `evidence_support`, `tactic_catalogue_version`.
- `eligible_tactics(..., metric_ids)` ignores `metric_ids` (compat parameter).

## Before / after

| Context | Before | After |
| --- | --- | --- |
| Streams primary, IG channel | `metric mismatch` on Story/Carousel/FB | Story/Reel may appear as planning or transfer hypothesis |
| Empty primary bundle | All content tactics skipped | Strategically fit tactics with `planning_hypothesis` basis |
| Evidence label | Often implied from primary metric match | Only when refs support tactic `observable_metrics` proposition |

## Tests

```bash
SOCIALS_MANAGER_LLM_DISABLED=1 .venv/bin/python manage.py test \
  tests.test_stage3_planning_amendment tests.test_stage3_repair tests.test_stage3 -v 2
```

**Result:** 34 passed (Oct 2026).

## Real-data limitations

- Owner DB is not seeded by tests. Sparse Spotify/Instagram observations still yield honest gaps on the primary bundle; supporting tactics may appear without empirical backing.
- Instagram live metrics and Spotify `llm_ingest` policy gates unchanged.

## Owner review checklist

- [ ] Follower-growth preview includes a relevant Story with planning/transfer basis (not evidence-backed without refs).
- [ ] Release + streams primary shows IG support tactics without metric mismatch noise.
- [ ] Why and Strategy show role, proposition, and composition policy where applicable.
- [ ] Ask cites deferred/excluded tactics when a campaign has an accepted recommendation.
- [ ] Outcome progress and findings still require compatible metrics.
- [ ] Stage 4 forecast gate still deferred.
