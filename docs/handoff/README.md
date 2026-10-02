# Normative handoff copy

Byte-identical copies of the current normative handoff documents, taken on 2 October 2026 from the private handoff root (`../../handoff/`, ignored by Git). Every file was checked against the handoff `MANIFEST.json` SHA-256 values at copy time.

Included: `START-HERE.md`, `AGENTS.md`, `spec/`, `execution/` (except the `AGENT-STATE.json` template), `contracts/` and `research/`.

Not included, by design: `data/real-inputs/` (private CSVs), `reference/` (prototype, POCs and the import investigation with its derivative database), `archive/` (history and original ZIPs), `verification/` and `tools/`. Relative links in these documents that point to those folders resolve only inside the original handoff.

Do not edit these files to record progress. Changes to requirements, thresholds or decisions are recorded as ADRs in `docs/adr/`; live progress is in `/execution/AGENT-STATE.json`.
