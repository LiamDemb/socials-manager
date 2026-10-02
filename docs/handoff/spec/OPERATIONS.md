# Local operation, recovery and deployment

## Initial supported deployment

One persistent machine, one band data root, local browser and loopback server. The reference stack should ship a concise install/start/stop/update/backup/restore procedure using audited pinned dependencies. Select the owner's actual OS/hardware when implementing packaging, not an assumed Linux-only deployment. No AWS database or hosting procurement is required.

Use a production-capable local server configuration for the final release, not a debug development server. Keep data outside build/install directories. Start one app and one leased job worker through a simple service/launcher. The machine can be offline/asleep; show last collection/data-through and recover due jobs on wake without pretending missed observations exist.

## Secrets and local security

Store tokens in an OS secret store or tightly permissioned local secret file/environment with an explicit `secret_ref`; never in observations or export artifacts. Persist required refresh state safely, redact logs and rotate/disconnect correctly. The application’s no-login choice does not waive provider authentication or secure writes.

Bind to loopback; validate allowed Host/Origin, enable same-origin CSRF protections, limit payloads and use parameterised queries/escaped rendering. Keep debug/error traces away from normal product views. Approved fetch hosts/redirects avoid private-network SSRF. Uploaded filenames cannot choose paths. No fan-level personal profiles, account passwords or email addresses are necessary for initial aggregates.

## Backup and restore

Create a SQLite-consistent snapshot using the backup API or a verified stopped/checkpointed procedure. Do not copy a live WAL database's main file alone. Preserve the referenced immutable imports/assets/eligible dataset/model metadata with hashes and a manifest at the same logical snapshot; quiesce concurrent mutation/deletion during manifest capture where needed. Secret backup is separately protected, optional and explicit.

Default run: backup before migrations/destructive maintenance and a daily backup when running, with bounded retention, visible last success/failure and periodic verified copy off the same disk to an owner-approved location. OS disk encryption/protected backups are recommended. Do not claim plain SQLite encrypts at rest.

Restore to a new temporary root first: verify manifest/hash/schema version, SQLite integrity/foreign keys, observation counts/sample values, file references and app smoke flow. Promote only after success, with current data backed up and a clear rollback. Restore cannot automatically resurrect source data that must remain deleted; policy/tombstone reconciliation is part of recovery.

Test restore, not just backup creation. A successful process exit without readable restored data is not acceptance.

## Upgrade and rollback

Each stage has a version/tag, migration plan, tested backup and smoke script. Run upgrades against a restored copy before owner data. Separate additive migrations from destructive changes; keep rollback via compatible app release + snapshot when schema downgrade is unsafe. Never wipe the data root to fix a failed migration.

Keep the last owner-accepted stage running until the next passes. Model/collector flags can be disabled independently without losing campaign/execution/import functionality. Missing providers stay visible, not green “connected”.

## Diagnostics

Track app/schema/runtime version; SQLite journal mode/version; last successful backup; worker heartbeat/expired leases; per-source last success/error, data-through, coverage and next run; import reconciliation; invalidated findings/proposals; model artifact/benchmark/status. Logs contain IDs/counts/safe codes, not tokens/full private payloads by default.

Expose a compact Sources/Settings health view and export a sanitised diagnostic report for the owner/agent. Offline inference can be Pending/Unavailable without blocking data collection. Clock/timezone disagreements are surfaced; server UTC drives execution status.

## Instance reset and second band later

Current implementation provides normal migrations and one configured data root, not workspace provisioning. Future clean instance procedure: archive/backup old root; create new root/config/instance ID; migrate an empty DB; seed definitions only; connect new accounts; import new band's data. Do not copy old source tokens, raw files, learned parameters, reviews, cache or outcome contracts.

A future Makefile can automate those steps. It is deliberately out of the current development plan. A reset must require an explicit destructive command/confirmation and backup; the normal app must never initialise over an existing DB silently.
