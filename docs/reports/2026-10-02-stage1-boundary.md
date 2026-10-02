# Stage 1 boundary report (2 Oct 2026)

Scope: S1-01 to S1-06. Stage 2 has not started and waits for owner review.

## Automated results

Full suite: 85 tests, all Passed, none skipped. Run with `BAND_EVIDENCE_REAL_FIXTURES` pointing at the original handoff CSVs, read in place. Browser tests ran in installed Google Chrome through Playwright.

| Case | Result | Evidence |
| --- | --- | --- |
| AC01 Exact real CSV ingestion and round trip | Passed | Real fixtures: 2,004 source rows, 9,018 values, exact dates and values, artist and song totals kept separate, lossless Spotify-shaped and common-format exports (`test_import_real`) |
| AC02 Replay, rename, overlap, conflicts | Passed | Real replay and renamed replay add no facts; overlap adds only new days; unapproved conflict rolls back; approved revision immutable (`test_import_real`, `test_import_rules`) |
| AC03 Invalid and stale imports | Passed | Rejections, size and empty limits, stale preview and stale policy cannot commit; invalid upload shown, not stored |
| AC04 Contribution undo | Passed | Two supporting imports, undo keeps the surviving contribution and reconciles the active version |
| AC05 Identity and relationships | Passed | Filename is not identity; song files map only to recordings; audience files only to own artist; pending identity until link and confirmed date |
| AC06 Campaign-first outcomes | Passed | Identical outcome is shared, not copied; different window is a separate contract; only selected activities are created; idempotent approval |
| AC07 Metric algebra and coverage | Passed | 15 cases: sums, latest snapshots, gains need a compatible baseline, ratio undefined is not zero, Unknown and Partial visible |
| AC08 Execution clock and terminal states | Passed | Derived Upcoming, Due today, Overdue, Unscheduled; daylight saving gaps; no future completion; history immutable |
| AC09 Completion versus outcome | Passed | Completion changes no metric; a later compatible observation does |
| AC10 Revisions and idempotency | Passed | Concurrent edits, same idempotency key, competing imports, double commit (real threads on a file database) |
| AC11 Persistence and restart | Passed | Real processes: init, write, restart, read back; no seeded metrics; init never overwrites |
| AC12 Evidence tabs | Passed | One tablist, fixed order and URLs, filter kept across tabs, drill-down to observation and source, Back and browser history (`test_browser`) |
| AC13 Nested dialogs | Passed | Activity, Why?, Source, Back; typed draft, open sections, scroll and focus restored; browser back and forward; discard prompt; save in a nested frame re-fetches the activity; deep links rebuild the stack |
| AC30 Evaluation ledger | Passed | As-of cutoffs exclude later availability and revisions; baselines and rolling splits on synthetic data; prospective ledger saved before the outcome; Spotify fitting Blocked by policy; real history reports Insufficient data (5 active streaming days of 1,002) |
| AC35 Backup, upgrade, boundary | Passed | Verified backup before upgrade and daily; restore to a new folder; tampered backup rejected; promote refused while running; data root inside repo refused; non-loopback 403; CSRF; strict CSP |
| AC25 Responsive accessibility | Not run (manual parts) | Automated part Passed: no page overflow and dialog actions reachable at 360x640, 768x1024, 1440x900 and 812x375 with a 5,000-character brief. 200% zoom, keyboard-only and screen reader passes are manual checks due by the release stage |

Also checked by hand in Chrome against the real data: Today trend cards, the creation flow for a Better Man single, campaign calendar and outcomes, Evidence, Sources and import preview, Settings, the 360px phone layout and the menu. A fresh install through `bin/band-evidence` initialises, serves, rejects a foreign Host header, takes its first backup and stops both processes cleanly.

## Fixed during verification

- A focus-triggered refresh replaced the page even when nothing had changed, which could swallow a click. It now skips identical content and runs at most every 15 seconds on focus.
- The campaign creation default measure was Instagram followers, which has no source. It now picks a sourced measure for the item type (Song streams for a single).
- A hidden table label made the Observed data page overflow sideways on phones.
- The phone month grid truncated titles to two letters. Phones now open the list view unless Month is chosen.
- The closed phone menu's shadow showed at the left edge, and its links were still in the tab order.

## Blockers and open gates

| Capability | State | What unblocks it |
| --- | --- | --- |
| Automatic Spotify retrieval | Blocked | Spotify for Artists has no analytics API. Reviewed CSV upload is the supported path |
| Spotify fitting, inference, LLM use | Blocked | Owner decision on Spotify data-use purposes |
| Validated forecasts | Insufficient data | More prospective history; 5 active streaming days is not forecast history |
| Better Man canonical identity | Pending | Track URL or ISRC and confirmed release date (Settings or catalogue) |
| Instagram (Meta) metrics | Not run | Stage 2 probe with an authorised professional account |
| Pre-save and ticket data | Not run | No provider selected; manual entry comes later |

## Proposed next stage

Stage 2 (S2-01 to S2-06): authorised Meta capability probe, the leased collector with source health, reviewed context and curated peers, reproducible findings with observation drill-down, contextual inspiration and scoped reports, then the artist-wide dashboard with source acceptance. It starts after owner review of this slice.
