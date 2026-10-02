# Stage 2 boundary report (2 Oct 2026)

Includes rename to **Socials Manager** and tasks S2-01 to S2-06. Stage 3 not started.

## Rename verification

| Check | Result |
| --- | --- |
| Python package `socials_manager` imports | Passed (`manage.py test`, 91 tests) |
| Launcher `bin/socials-manager` | Passed |
| UI title "Socials Manager" | Passed (templates) |
| Default data root `~/Library/Application Support/SocialsManager/` | Passed |
| Legacy `BAND_EVIDENCE_*` env aliases | Passed (read-only fallback) |
| `migrate-data` refuses overwrite | Passed (command + tests) |
| Legacy backup format restore | Passed (`band-evidence-backup-1` still accepted) |
| Handoff `docs/handoff/` unchanged | Passed |
| Existing owner data on disk | Not run (no BandEvidence folder present on build machine) |

## Automated acceptance (Stage 2 slice)

| Case | Result | Notes |
| --- | --- | --- |
| AC14 Meta capability | Passed (Blocked live) | `probe_instagram` writes sanitised report; @opalseason_ recorded |
| AC15 Collector | Passed | `collect.source` job returns blocked without credentials; no fake metrics |
| AC16 Findings lineage | Passed | Published finding stores bundle + lineage |
| AC17 Reviewed context / peers | Passed | Fixture peer reviewed; live collection blocked |
| AC19 Inspiration | Passed | Reference model and page |
| AC20 Pre-save/ticket | Partial | Metric contracts exist; manual observation path only |
| AC26 Purpose enforcement | Passed | Spotify fit denied; Instagram purposes unresolved |
| AC27–AC31 | Passed / Blocked as designed | Deletion/revocation hooks via source state; dashboard uses real Spotify freshness; Instagram live Blocked |

Full suite: **91 tests, all Passed** (run with `SOCIALS_MANAGER_REAL_FIXTURES` for real CSV tests).

## Live integration evidence (sanitised)

- Instagram `live_integration`: **Blocked** (no `secrets/instagram.json`)
- Spotify automatic retrieval: **Blocked** (CSV path only)
- Example probe output fields: `handle`, `route`, `timezone_semantics: unknown until live payload`, per-metric unsupported states

## Remaining blockers

- Meta developer app, permissions and long-lived token ([docs/META-SETUP.md](../META-SETUP.md))
- Better Man identity confirmation in Settings (track URL and date stored via `sync_owner_catalogue`, state pending)
- Pre-save and ticket provider selection
- Spotify source-use permission before any modelling gate opens
