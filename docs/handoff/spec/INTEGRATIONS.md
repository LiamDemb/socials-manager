# Integrations, capability tests and source traceability

## Adapter boundary

All providers return canonical entities, metric definitions, scoped observations, raw lineage and capability/coverage states. Transport is replaceable: `SpotifyArtistAnalyticsProvider` begins with reviewed CSV; automatic retrieval is not implied. Keep format/parser revisions explicit and capability flags per metric/action, not a single “connected” boolean.

Source policy records separate collect/store/display/descriptive-derive/statistical-fit/model-infer/LLM-ingest/export purposes with allowed/denied/unresolved, conditions, assessment reference and dates. Unknown denies the affected operation. A policy can allow a display but block training. Derived data keeps its inputs' restrictions. Do not send restricted values to synthesis/Ask through an indirect summary.

## Initial integration set

| Source/channel | Initial path | Real verification required |
| --- | --- | --- |
| Spotify own artist/recording outcomes | Supplied Artists CSVs; regular manual export/import | Explicit mapping, schema/metrics, freshness/revisions and purpose assessment; no Web API analytics shortcut |
| Instagram own professional account | Authorised Meta adapter after capability probe; reviewed imports/manual facts as fallback | Route/API version, account eligibility/permissions, timestamps, insights per format, token lifecycle, pagination/quota and deletion |
| Instagram peer public content | Only permitted verified public/API/import route | Observable fields/coverage; no private reach/conversion/online-follower claims |
| Pre-saves | Release/provider-scoped reviewed report/manual observation first | Counts semantics, provider identity, duplicate/revision and source-use contract; automatic adapter after selection |
| Ticket sales | Event-scoped ticket report/manual observation first | Net issued/paid/refund definition, snapshot versus flow, mapping and totals; adapter optional after verified report |
| Facebook | Plan/manual execution and permitted reports | Relevant local audience and Page/event route before automated collection |
| YouTube/Shorts | Plan/manual execution and permitted reports | Channel/media metric scope before an automatic analytics adapter |
| Email/newsletter | Brief/execution/aggregate report | Authorised opted-in list; no storing fan-level addresses or sending automatically in initial scope |
| Merch | Item-scoped report/manual observation | Net units/revenue/refunds/currency; no store provider assumed |
| MusicBrainz | Later bounded identity/release lookup | Canonical links/disambiguation, licence/caching/rate policy, external IDs separately reviewed |
| Last.fm/ListenBrainz discovery | Deferred optional adapter | Intended-use/ownership/coverage assessment before adoption; sparse artist coverage is expected |

Planning format support does not imply a connected analytics/publishing API. Instagram Feed image/carousel, Reels and Stories; Facebook post/Reel/event; YouTube video/Short; email; pre-save/link/profile/pitch actions; manual outreach; internal task/milestone/review are supported planning types. TikTok is excluded by the owner restriction. X is deferred unless actual audience need justifies it. No automatic publishing is in scope.

## Spotify findings and boundaries

The real importer/re-export POC proves both supplied shapes, reconciliation and idempotency. Official support confirms CSV exports for song streams and Audience timelines, and UTC-day measurement. It does not prove automatic download or model-use permission.

The Web API Developer Policy restricts analytics and model ingestion; Artists exports have a distinct route and incorporated User Guidelines. Those guidelines also contain model training/ingestion restrictions. Internal/non-commercial use is not an established exemption. The precise own-band numerical processing route remains unresolved. This is an engineering capability assessment, not a legal conclusion. See research/SOURCES.json and the preserved investigation/assessment.

Keep statistical fitting/backtesting/ML/LLM processing of affected Spotify observations disabled until the applicable intended use is established. Do not rename training “Bayesian updating” to bypass the gate. Import/descriptive use and model use are assessed separately; do not assert that all CSV uses are forbidden or that technical parsing establishes all rights. No Spotify message was sent in this work.

Specific clarification for owner/authorised adviser: may the band's authorised team privately retain/display its aggregate Audience/song CSVs and fit/backtest local numerical forecasts, without public distribution, sale, audio ingestion, personal fan profiles or language-model training? Seek separate answers for descriptive processing and numerical/model use. Do not send this request without explicit owner instruction.

Native Countdown Pages apply to eligible new albums/EPs, not singles; they expose scoped pre-save analytics. Check current eligibility rather than hard-code a cached threshold. A single needs another identified report/provider. The supplied CSVs contain no pre-saves; artist saves/link clicks cannot substitute.

## Meta and temporal intelligence

Prior official indexed research documented optional `online_followers` with a last-30-days window. The full Meta Account Insights page was rate-limited/unavailable; the 1 Oct recheck did not verify a live response. The official collection describes professional-account APIs but its dynamic body is incomplete here. **No authenticated account, hour/day payload, timezone, segment breakdown or field availability is verified by this handoff.**

The agent must select and pin the current authorised Instagram login route. Account insights and peer Business Discovery may require different routes/permissions; do not assume one token enables both. Record current app mode, account class, permission approvals, any Page relationship, API version and capability result without leaking secrets.

Temporal probe checklist:

1. Fetch own media and preserve actual publication timestamp, raw offset/timezone and media/format identity.
2. Test own available per-format metrics and repeated snapshots. Preserve lifetime/cumulative versus period semantics; capture ephemeral Stories while accessible. Missing historic Story results are gaps.
3. Probe optional follower online/availability metric and record actual dimensions, bucket dates, timezone and support status. An hourly distribution without dated buckets cannot yield day × hour; unrelated demographics cannot yield segment × hour × format.
4. Reject hour ranking if timezone is unknown. No LLM guesses offsets.
5. Verify token refresh/expiry/revocation, pagination, partial permissions, 429/retry signals, cursor recovery, deleted media and schema-change behaviour.
6. Publish an adapter capability report: supported/unsupported/denied/delayed/stale/insufficient/unknown-timezone, actual sample shape with secrets stripped, account scope and coverage.

Own performance can be derived by actual local weekday/hour with common post-age metrics and reviewed format/context. This is an observational window preference, not causal “optimal time”. Availability is a secondary prior, not proof of conversion. Peer posting times are not our audience's availability.

## Collector behaviour

Begin daily account/media snapshots and accessible paginated backfill; backfilled current counts are dated as collected now. Add early-age sampling only where needed to produce common-age evidence. Provider-specific limits are configurable and verified, not copied from old informal research.

Collect outside the DB transaction, then atomically commit observations/cursor and job completion. Respect provider retry/backoff, recovery leases and bounded failures. Sleep/offline means collection gaps, never invented samples. Refresh after wake, disclose gaps and prioritise supported recent data. A disconnected source cancels work and follows its deletion policy.

## External page traceability

Store source name/URL, published date if provided, retrieved date, extracted claim, permitted stored excerpt/metadata, transformation and influence on a finding/recommendation. Missing publication date stays unknown. Distinguish product capability documentation from campaign-effect evidence.

Sources behind a recommendation appear in Why? → evidence → source drill-down, not every calendar card. No arbitrary web research becomes automatically trusted: use a bounded retrieval process, source review, date/quality/context checks and applicable purpose policy. Scraping/unofficial Bandcamp endpoints in the original vision are historical suggestions, not authorised collection paths.
