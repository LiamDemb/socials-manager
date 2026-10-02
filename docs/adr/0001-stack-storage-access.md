# ADR 0001: Stack, storage and local access

Status: Accepted (Stage 1, 2 Oct 2026)

## Context

One internal installation for one artist. The handoff sets the reference stack (Django, SQLite, server-rendered templates, original browser JavaScript, one leased worker), requires loopback-only access with no login, and excludes dependencies with Chinese ownership or unknown provenance.

## Decisions

1. **Runtime.** Python 3.14.4 with Django 5.2.17 (LTS line) and waitress 3.0.2 as the WSGI server. Four runtime packages in total, hash-pinned in `requirements.txt` and audited in `docs/dependencies.json`. Browser tests use Playwright 1.63 from `requirements-test.txt` against the installed Google Chrome. No browser download and no Node runtime.
2. **Storage.** One SQLite file (`app.sqlite3`) with `foreign_keys=ON`, `synchronous=FULL`, a 20 second busy timeout and `BEGIN IMMEDIATE` transactions. WAL is used only when the linked SQLite has the WAL-reset fix (3.51.3+, or the fixed backports); otherwise the journal falls back to `delete`, and diagnostics show which. Python links SQLite 3.53.0, so WAL is on. The macOS `sqlite3` CLI (3.43.2) must not be used against a live database.
3. **Data root.** `BAND_EVIDENCE_DATA_ROOT`, default `~/Library/Application Support/BandEvidence/`. It holds the database, `instance.json`, the secret key (0600), original upload bytes, backups and run files. Startup refuses a data root inside the repository. Real regression fixtures are read in place through `BAND_EVIDENCE_REAL_FIXTURES` and never copied into the repository or the owner database.
4. **Access.** `serve` binds 127.0.0.1 only. Middleware returns 403 to any non-loopback client, and Host headers other than `127.0.0.1` or `localhost` are rejected. CSRF tokens are required for every mutation, each mutation needs an `Idempotency-Key`, and mutable records carry an optimistic `revision`. Responses carry a strict CSP (`default-src 'self'`, no inline script or style, `frame-ancestors 'none'`), `Cache-Control: no-store` and Django's `nosniff` and same-origin referrer defaults.
5. **Static files.** Django serves `web/static` directly through an allowlisted route (`css/` and `js/` file names only). There is no collectstatic step and no CDN.
6. **Worker.** One process (`run_worker`) leases jobs from a SQLite table with an expiry, so a crashed worker's job is recovered. In Stage 1 it runs the daily verified backup.
7. **Upgrades and recovery.** `start` takes a verified backup before applying migrations. A backup is a consistent SQLite copy plus original files and a SHA-256 manifest. `restore` writes into a new folder and verifies it. `--promote` switches only when the app is stopped.

## Product rules fixed in Stage 1

- Outcome modes are `total` (sum within the window), `gain` (end value minus the baseline at window start) and `level` (latest value against a target). Partial or missing coverage reports Unknown or Partial, never zero.
- Weekly capacity is a warning, never a block.
- Completing an activity records an execution event and never changes outcome progress.
- Spotify source policy (assumption, pending owner confirmation): collect, store, display and descriptive comparison are allowed. Statistical fitting, backtesting, inference and any LLM ingestion are Blocked until resolved. The evaluation layer enforces this before it runs a query.

## Consequences

The app is easy to run and back up, with no service overhead. Concurrent writers serialise on SQLite, which is acceptable for one owner plus one worker and is covered by the concurrency tests. Anything that needs remote access, multiple users or a hosted database is out of scope and would need a new ADR.
