# Stage 2 integration report (2 Oct 2026, revised)

MusicBrainz, Last.fm and Meta are in scope for Stage 2 (see `docs/execution/SCOPE-STAGE2-INTEGRATIONS.md`). Stage 3 not started.

## Automated tests

**97 tests, all Passed** (7 skipped: live integration suite unless `SOCIALS_MANAGER_LIVE_TESTS=1`).

| Area | Result |
| --- | --- |
| Provider adapters (mocked HTTP) | Passed |
| Peer promotion / collection services | Passed |
| Stage 1 regression | Passed |

## Live evidence (sanitised)

Run on 2 Oct 2026 with owner `.env` (values not recorded here).

### MusicBrainz (AC40)

- Query `artist:"Opal Season"`: **not_found** (no ambiguous merge performed).
- Adapter obeys User-Agent and caches JSON under `cache/api/musicbrainz/`.

### Last.fm (AC41)

- `artist.getSimilar` for **Opal Season**: **found** with zero similar artists returned (sparse catalogue entry). API key accepted.
- Use reference seed artists when similarity is empty; candidates still require review (AC42).

### Meta own account (AC43)

- **Route detected:** `instagram_login_basic` via `graph.instagram.com`.
- **Retrieved:** `user_id`, `username` (`opalseason_`), `account_type` (`MEDIA_CREATOR`).
- **Unavailable on this route:** `followers_count`, `media_count`, insights, `online_followers`.
- **Business Discovery:** **Blocked** (`business_discovery_supported: false`) until Facebook Page + Graph Page token is configured ([docs/META-SETUP.md](../META-SETUP.md)).

### Peer Business Discovery (AC44)

- **Blocked** with current configuration. `probe_meta --peer <username>` will run once Page-linked token is available.

### Collection queue (AC45)

- Implemented: `PeerCollectionEntry`, worker `collect.source` / `collect_peers`, health JSON per peer, no fabricated metrics.

## Owner configuration blocker

Connect **Facebook Page** to @opalseason_ and supply a **Page access token** in `META_ACCESS_TOKEN` to unlock Business Discovery and full own-account metrics for the ~50 peer cohort.

## Smoke checklist

- [ ] `python manage.py probe_meta` → own account **ok**, Business Discovery **blocked** or **ok**
- [ ] `python manage.py musicbrainz_lookup --artist "Your Name"`
- [ ] `python manage.py lastfm_discover --artist "Opal Season"` (try a reference artist if empty)
- [ ] Peers → Discover → Promote one candidate with explicit `@instagram`
- [ ] `python manage.py collect_peers` after Meta Page token works
- [ ] `bin/socials-manager test`
