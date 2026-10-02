# Stage 2 integration scope (supersedes deferred handoff rows)

Effective 2 Oct 2026. Overrides `docs/handoff/spec/INTEGRATIONS.md` table rows for MusicBrainz, Last.fm and Meta peer collection only. All other handoff rules remain binding.

## MusicBrainz

- **Purpose:** Bounded artist/release lookup for canonical identity, disambiguation and relationships.
- **Transport:** MusicBrainz WS/2 JSON over HTTPS; `User-Agent: SocialsManager/0.2 (+https://localhost; contact=owner@local)`; 1 request/second.
- **Policy:** [MusicBrainz data licence](https://musicbrainz.org/doc/MusicBrainz_API); store provider IDs and provenance; cache responses under the data root.
- **Rules:** Never auto-merge ambiguous artist search results. Owner selects an MBID or leaves identity pending.
- **Commands:** `python manage.py musicbrainz_lookup --artist "…"` / `--mbid …`

## Last.fm

- **Purpose:** `artist.getSimilar` for **peer candidate discovery** only.
- **Transport:** Audioscrobbler API; `LAST_FM_API_KEY` from `.env` (never committed).
- **Policy:** [Last.fm API Terms](https://www.last.fm/api/terms); similarity is not campaign evidence.
- **Rules:** Human review before `PeerProfile` promotion. Never infer Instagram handles from artist names. Use reference seed artists when Opal Season is sparse in Last.fm.
- **Commands:** `python manage.py lastfm_discover --artist "Opal Season"`; UI **Discover similar** on Peers.

## Meta (own account + peers)

- **Inspect first:** `python manage.py probe_meta` writes `reports/meta-probe-latest.json` (sanitised).
- **Routes:**
  - **Instagram Login** (`graph.instagram.com`): own `user_id`, `username`, `account_type` only with current token. No follower counts or Business Discovery.
  - **Facebook Login + Page-linked professional account** (`graph.facebook.com`): required for `business_discovery`, follower counts and insights.
- **Peers:** Up to **50** curated peers. Business Discovery only for peers with an **owner-supplied** `instagram_username`. Resumable queue (`PeerCollectionEntry`) with batch collection, retries and per-peer health. No fabricated reach, saves or conversions.
- **Secrets:** `.env` in repo root (gitignored): `INSTAGRAM_ACCESS_TOKEN`, `META_ACCESS_TOKEN`, `META_APP_ID`.

## Acceptance additions

See `acceptance-cases-stage2.json` (AC40–AC46).
