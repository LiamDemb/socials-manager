# Socials Manager

Internal, single-artist tool for planning campaigns and measuring them against imported Spotify for Artists data (and, when authorised, other sources). It runs on this Mac only (127.0.0.1) and keeps its data outside this folder.

## Requirements

- macOS with Python 3.14 (`brew install python@3.14`)
- Google Chrome, only for the browser tests

## First run

```sh
bin/socials-manager setup
bin/socials-manager init --artist "Opal Season" --timezone Australia/Perth
bin/socials-manager start
```

Open <http://127.0.0.1:8765>. Ctrl+C stops the server and the background worker.

Data lives in `~/Library/Application Support/SocialsManager/`. To use another folder:

```sh
export SOCIALS_MANAGER_DATA_ROOT="$HOME/SocialsManager-trial"
```

The folder must be outside this repository. `init` never overwrites an existing installation.

### Migrating from Band Evidence

If you already have data under `~/Library/Application Support/BandEvidence/`:

```sh
bin/socials-manager migrate-data
export SOCIALS_MANAGER_DATA_ROOT="$HOME/Library/Application Support/SocialsManager"
```

This takes a verified backup of the legacy folder first and refuses to copy over an existing SocialsManager database.

### Owner catalogue facts

After Better Man exists in the catalogue (import or create):

```sh
python manage.py sync_owner_catalogue
```

This stores the owner-supplied Spotify track URL and release date without confirming identity (still pending until you confirm in Settings).

## Spotify data

Export Audience and song CSVs from Spotify for Artists, then **Sources → Import CSV**. Reviewed import only; there is no analytics API.

## Instagram / Meta

Live integration is **Blocked** until you complete [docs/META-SETUP.md](docs/META-SETUP.md). Run `python manage.py probe_instagram` after storing a token locally (never in the repo).

## Backups

- `start` backs up before upgrades; the worker backs up daily.
- `bin/socials-manager backup` / `backup --list`
- `bin/socials-manager restore <folder>` then `--promote` with the app stopped.

## Tests

```sh
bin/socials-manager setup --test
bin/socials-manager test
export SOCIALS_MANAGER_REAL_FIXTURES="$HOME/Downloads/band-evidence-development-handoff/data/real-inputs"
```

Legacy env names (`BAND_EVIDENCE_DATA_ROOT`, etc.) still work but are deprecated.

## Documentation

- [docs/PROJECT-CONTEXT.md](docs/PROJECT-CONTEXT.md)
- [docs/handoff/](docs/handoff/) (authoritative spec; historical product name)
- [docs/adr/](docs/adr/)
- [execution/AGENT-STATE.json](execution/AGENT-STATE.json)
