# Band Evidence

Internal, single-artist tool for planning campaigns and measuring them against imported Spotify for Artists data. It runs on this Mac only (127.0.0.1) and keeps its data outside this folder.

## Requirements

- macOS with Python 3.14 (`brew install python@3.14`)
- Google Chrome, only for the browser tests

## First run

```sh
bin/band-evidence setup
bin/band-evidence init --artist "Opal Season" --timezone Australia/Perth
bin/band-evidence start
```

Open <http://127.0.0.1:8765>. Stop with Ctrl+C, which stops the server and the background worker.

Data lives in `~/Library/Application Support/BandEvidence/`. To use another folder (for a trial run, say), set it for every command:

```sh
export BAND_EVIDENCE_DATA_ROOT="$HOME/BandEvidence-trial"
```

The folder must be outside this repository. `init` never overwrites an existing installation. Use `start --port 8770` for a different port.

## Getting Spotify data in

Spotify for Artists has no analytics API, so data comes in by CSV. In Spotify for Artists, export the audience timeline (whole artist) and any song's streams timeline. In the app, go to **Sources** and choose **Import CSV**. You see a preview first. Nothing is stored as data until you commit, the original file is kept unchanged, and any import can be undone.

## Backups

- `start` makes a verified backup before applying any upgrade, and the worker makes one daily.
- `bin/band-evidence backup` makes one now; `backup --list` shows them.
- `bin/band-evidence restore <backup folder>` restores into a new folder beside the data folder and verifies it. Add `--promote` (with the app stopped) to switch to it.

## Tests

```sh
bin/band-evidence setup --test     # adds Playwright for browser checks; uses installed Chrome
bin/band-evidence test
```

The real-CSV regression tests read the original fixtures in place and report Not run unless you point at them:

```sh
export BAND_EVIDENCE_REAL_FIXTURES="$HOME/Downloads/band-evidence-development-handoff/data/real-inputs"
```

## Documentation

- `docs/PROJECT-CONTEXT.md`: orientation and open gates
- `docs/handoff/`: the specification (authoritative)
- `docs/adr/`: engineering decisions
- `docs/reports/`: stage and verification reports
- `execution/AGENT-STATE.json`: development checkpoint
