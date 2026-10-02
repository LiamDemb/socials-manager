# Stage 3 report (2 Oct 2026)

Evidence-backed campaign drafts, scheduling records, experiments/adaptations, Ask and local LLM adapter. **Stage 4 not started.**

## Tests

**108 automated tests: Passed** (8 skipped live integrations).

| Layer | Result |
| --- | --- |
| Stage 3 (`tests/test_stage3.py`) | Passed |
| Stage 1–2 regression | Passed |
| Live provider suite | Skipped unless `SOCIALS_MANAGER_LIVE_TESTS=1` |

## Stage 2 foundation (re-verified)

| Capability | Status | Notes |
| --- | --- | --- |
| Meta own account | **Live OK** | Graph route; followers/media via `META_ACCESS_TOKEN` |
| Business Discovery | **Live OK** | `business_discovery_supported: true` after token split fix |
| MusicBrainz | **Live** | API works; Opal Season may be `not_found` |
| Last.fm | **Live** | API works; sparse similarity for own artist |
| Spotify CSV | **Passed** | Mocked + regression tests; LLM ingest **policy denied** |

## Local LLM (S3-04 / AC32)

- **ADR:** [docs/adr/0003-local-llm-mlx-llama32.md](../adr/0003-local-llm-mlx-llama32.md)
- **Default model:** `mlx-community/Llama-3.2-3B-Instruct-4bit` via optional `mlx-lm`
- **Qualification:** `python manage.py qualify_llm` — **passed** on deterministic fallback (MLX not in core venv)
- **Enable MLX inference (owner, once):**
  ```sh
  .venv/bin/pip install mlx mlx-lm
  .venv/bin/python manage.py qualify_llm
  ```
- **No cloud fallback;** `SOCIALS_MANAGER_LLM_DISABLED=1` forces template fallback

## Product journeys (implemented)

1. **Create campaign** — step 2 “Include evidence-backed content suggestions” → preview merges operational + evidence activities; citations validated; Spotify LLM blocked.
2. **Scheduling** — `SchedulingDecision` rows on create when scheduling JSON present; fallback basis disclosed.
3. **Ask** — `/ask` + `POST /api/ask` with sanitised prompts and citation checks.
4. **Adaptations** — `AdaptationProposal` accept/reject via API; duplicate fingerprint suppressed.
5. **Experiments** — model + services; causal claims rejected at review.

## Smoke checklist (owner)

- [ ] `bin/socials-manager test`
- [ ] `python manage.py probe_meta` and optional `--peer <username>`
- [ ] `python manage.py qualify_llm` (after optional `mlx-lm` install)
- [ ] Create **growth** campaign with evidence checkbox → review shows proposed Reel/content
- [ ] **Ask** a question with some imported Spotify/Instagram data present
- [ ] Confirm Sources → Instagram **Connected** and peer discovery **Available**

## Remaining blockers

- **MLX weights:** optional install for real neural inference (fallback is production-safe but labelled)
- **Spotify LLM/fit:** source policy unchanged
- **Stage 4:** browser/accessibility matrix, forecast qualification gate
