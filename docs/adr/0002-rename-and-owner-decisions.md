# ADR 0002: Rename to Socials Manager and owner decisions (2 Oct 2026)

Status: Accepted

## Rename

- **Display name:** Socials Manager
- **Repository slug:** socials-manager (unchanged path)
- **Python package:** `socials_manager` (was `bandevidence`)
- **Launcher:** `bin/socials-manager` (was `bin/band-evidence`)
- **Environment variables:** `SOCIALS_MANAGER_*` are canonical; `BAND_EVIDENCE_*` remain as deprecated aliases for data root, fixtures, port and secret key.
- **Data root default:** `~/Library/Application Support/SocialsManager/`
- **Legacy data:** `bin/socials-manager migrate-data` copies `~/Library/Application Support/BandEvidence/` after a verified backup; never overwrites an existing SocialsManager database.
- **Backups:** New backups use format `socials-manager-backup-1`; restores still accept `band-evidence-backup-1`.
- **Handoff:** `docs/handoff/` text is unchanged (historical product name Band Evidence).

## Owner decisions recorded

1. **Spotify CSVs:** Owner-supplied exports may be imported, stored, displayed and used for descriptive workflows per the handoff. No unrestricted collection or processing rights are assumed. Statistical modelling and AI ingestion stay **denied** in source policy until applicable **source-use permission** is established (not feature approval alone).
2. **Data root:** `~/Library/Application Support/SocialsManager/`
3. **Better Man:** Track [7n6t9MVmHySFjov060YHcf](https://open.spotify.com/track/7n6t9MVmHySFjov060YHcf?si=811e1c1e68ae46c9), release date 2026-09-25 owner-supplied but **unverified** until confirmed in Settings; identity stays **pending** (`sync_owner_catalogue` applies facts without auto-confirming).
4. **Instagram:** @opalseason_; Meta app access **UNSURE**. Live probe and collection remain **Blocked** until `docs/META-SETUP.md` is completed; adapter and fixture paths are in place.
