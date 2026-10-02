# Intelligence v2 handover (3 Oct 2026)

## Capability matrix

| Capability | Status |
| --- | --- |
| Analysis agenda + resolver + lineage cache | **Implemented and verified** (unit tests) |
| Peer media pagination, snapshots, coverage UI | **Implemented and verified** (fixtures; live Meta requires tokens) |
| Manual inspiration excluded from cohort | **Implemented and verified** |
| post_response / interval_response / temporal_window runners | **Implemented and verified** on fixtures |
| Bayesian qualification on owner data | **Implemented but data-gated** (sparse history; use `qualify_statistics` on synthetic) |
| PyMC absent on machine | **Genuinely blocked** → `dependency_unavailable`, not `insufficient_data` |
| DecisionContext in campaign preview | **Implemented and verified** |
| Claim metric/number checks | **Implemented and verified** |
| Timing evidence basis with refs | **Implemented and verified** |
| Stage 4 forecast gate | **Genuinely blocked** (out of scope) |

## Tests

```bash
SOCIALS_MANAGER_LLM_DISABLED=1 .venv/bin/python manage.py test tests.test_intelligence_v2 tests.test_stage3_planning_amendment tests.test_stage3_repair -v 2
```

Result: 23 passed (Oct 2026).

## Qualification (separate from unit tests)

```bash
.venv/bin/python manage.py qualify_statistics
.venv/bin/python manage.py qualify_llm   # requires MLX; fallback cannot pass
```

Criteria frozen in `intelligence/qualification_criteria.py`.

## Owner verification steps

1. Peers: confirm role, coverage fraction, expandable collected posts.
2. Inspiration: confirm manual-save disclaimer.
3. Campaign preview (follower growth): Story hypothesis without metric mismatch noise; planning notes for blocked/insufficient analyses.
4. Why: claims sections (strategic/transfer) on evidence activities.
5. Timing: fallback label unless timing evidence includes refs.
6. Experiment: close with inconclusive; adaptation accept applies diff once.

Stage 3 remains **open for consolidated owner review**. Not complete because tests pass or statistical names exist.
