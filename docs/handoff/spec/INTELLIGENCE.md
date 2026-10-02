# Evidence, recommendations, scheduling and learning

## Five different things

| Layer | Example | Producer |
| --- | --- | --- |
| Observed data | Four own Reels have compatible seven-day reach snapshots | Validated ingestion/query |
| Interpretation | A caption refers to a pre-release teaser | Rules or audited semantic extractor + review |
| Finding | A performance-led group had higher observed median reach in this sample | Versioned deterministic/statistical analysis |
| Recommendation | Try a performance-led Reel within the campaign's feasible window | Eligible tactic ranking + constrained synthesis |
| Creative suggestion | Ten-second rehearsal clip with the chorus hook | Editable template/local model, never effectiveness evidence |

The system learns through growing eligible history, corrected context, reviewed experiments and evaluated statistical updates. **It does not require fine-tuning an LLM on the band's database.** A local LLM is a replaceable extraction/synthesis component. A numerical forecast model is separate; both require permitted inputs and their own validation.

## Recommendation pipeline

1. Resolve current campaign/object/outcome/resource revisions and current time. Capture context: objective, dates/phase/time remaining, channel strengths, audience, budget/assets/capacity, completed work and results.
2. Filter source-use eligibility for the intended operation, identity/review state, metric compatibility, scope, post age, coverage/freshness and cutoff. Unresolved/excluded peers are ineligible.
3. Build a frozen evidence bundle with exact observation/interpretation/cohort/policy versions and transformations. Retrieve own history first for private outcomes. Peers contribute only comparable observable hypotheses; external context is explicitly sourced.
4. Compute findings with a versioned method: robust summaries/sample/missingness, relevant comparison and confounders. Evidence for engagement is not automatically evidence for streams, pre-saves or ticket conversion.
5. Derive campaign needs (role priorities from type/phase/context; `needs-v1`). Hard-exclude tactics only for genuine incompatibilities (channel, phase, prerequisites, policy). **Do not** require observable metrics to match the primary outcome for selection (ADR 0004). Assess **strategic fit** and **evidence support** separately. Rank and compose a small coherent set (`compose-v1`) with disclosed deferrals; the LLM does not choose the final activity set.
6. Templates or an audited local model turn each **selected** tactic and allowed refs into concise reasoning and a concrete execution brief. Planning hypotheses without empirical support are labelled honestly; they are not `evidence_backed`.
7. Deterministically validate schema, citation IDs/versions, target relevance, asset readiness, date/time/phase/dependencies, budget, shared capacity, duplicate intent, source policy and current revisions. Bad output is rejected/retried once or falls back; never repaired by inventing facts.
8. Present a draft with Why?, Timing and references. User edits/accepts/rejects. Revalidate before atomic acceptance and pin the final evidence/scheduling provenance.

For fixed inputs and rule versions, filtering/ranking/validation/tie-breaks are reproducible. Record model/hash, prompt/schema version, parameters, bundle ID, output hash and validation. Low temperature does not guarantee byte-identical inference. Retain concise rationale, not hidden chain-of-thought.

Retrieval starts with indexed SQLite queries over metric/scope, campaign purpose/phase, format, account, age, reviewed labels and source eligibility. Add SQLite full-text search for permitted captions/briefs if it improves browsing; verify the selected runtime capability. No vector database is needed initially. Optional embeddings would be derived model inputs with the same source-use, deletion and audit obligations, not a shortcut around traceability.

## Support, assumptions and abstention

Use qualitative support assigned by code from source quality, independent units, sample/coverage, comparability, freshness and target relevance. The LLM does not grade its own confidence. The example support policy is a provisional conservative rubric, not an empirical calibration or success probability. Review/tune it from actual evaluation; do not copy the demo's eight-post threshold as statistically established.

Show the short recommendation first. On demand show reason, finding, supporting observations, assumptions/limits, source links and method. Inspiration relevance, tactic support and predictive uncertainty are different. Temporal support may be weak even when tactic support is stronger.

No eligible evidence for the primary outcome: return evidence gaps, justified operational setup, and contextually relevant **planning hypotheses** (e.g. supporting Stories) with disclosed limits. Do not label those evidence-backed. Uncertain interpretations may remain Unknown. Unavailable inference must not disable campaign creation, execution or measurement.

## Temporal scheduling

Store a SchedulingDecision: requested relative date/window, hard date flag, feasible candidates/rejections, chosen UTC/local timestamp + IANA zone, timing input versions, source/limits, fallback basis, rule version and override history.

Policy:

1. Define feasible windows from anchor/phase, asset-ready/dependency dates, blackouts, available hours and shared labour/content limits. Hard release/show/milestone dates cannot move under a preferred window.
2. Compare own compatible performance at common measured age, reviewed format/context and verified publication timezone. Account for paid/organic/unknown exposure and audience/phase changes. Avoid selecting only successful posts.
3. Use optional verified follower-online availability as a separate secondary signal. No aggregate unrelated dimensions are joined into invented temporal segments.
4. Rank practical windows with versioned conservative rules. Prefer broad stable windows to false minute precision. Exact representative time and tie-break are practical choices, not proven unique optima.
5. If evidence is sparse/stale/confounded, timezone unknown or no compatible window feasible, use declared availability/campaign constraints and disclose fallback. Manual editing is always available, with conflicts surfaced.
6. Revalidate at approval. Existing approved times stay fixed; new evidence can create a reviewed change proposal. Manual date/time/format changes flag the previous rationale/experiment for review.

Default activity display: one compact `Timing: Own Reel history` / `Your schedule` / `Campaign constraint` link. Detail shows the chosen feasible window, short basis, source/sample and limitation. Never claim “best time” from audience-online counts alone.

The final prototype uses eight synthetic own Reel observations: four Tue/Thu evenings median 835 versus four Mon/Wed lunchtime median 455 at seven days. Day and hour vary together, so this cannot isolate separate weekday/hour effects. It selects a practical 18:00 within 18:00–20:00, sometimes within ±2 days while respecting phase/constraints. These values/windows are fixtures, not real artist policy.

## Capacity and resource logic

One artist's shared weekly labour budget plus per-format/content limits applies across active campaigns. Each activity has an editable effort estimate and priority; own campaign ceilings cannot override the global budget. Stories/email/outreach consume time even if not a substantial feed/video post. No post-count system is a financial budget optimiser.

New draft conflicts show alternatives: move within feasible window, reduce/delete work, change priority or explicitly approve a manual override with reason. Do not silently delete another campaign's work. Default caps come from user availability/setup, not invented “optimal frequency”. Budget checks enforce a ceiling and currency; no paid tactic/cost or spend is assumed without inputs.

## Adaptation

Trigger on matured compatible results, outcome pace/coverage changes, missed execution, revised context/identity/source eligibility, resources or key dates. Recompute eligible inputs before proposing. Default one pending adjustment per same campaign/reason/input fingerprint, with a configurable cooldown; new material input can supersede it. A single outlier should not cause repeated strategy churn.

A proposal records old/new values, changed evidence, reason, assumptions/limits, base revisions, affected experiments and manual edits. User Accept/Modify/Reject is transactional and idempotent. Stale evidence/base revision blocks acceptance. A rejected idea is not a failed experiment; it influences preference/cooldown separately from observed performance.

## Semantic extraction and grounded Ask

Semantic tasks use only permitted caption/context snippets and reviewed canonical candidates. Output labels, evidence spans, candidate links and abstention under JSON Schema. Model scores are uncalibrated unless separately validated. Human correction creates a version and invalidates dependent comparisons; no automatic rewriting of raw text.

Evaluate rules versus audited model on held-out permitted labels; split by campaign/artist where possible to prevent near-duplicate leakage. Report per-label precision/recall, ambiguous/unknown handling, invented-link rate, schema/source-span validity, resource use and failure recovery. Required hard checks: all accepted output parses, all referenced IDs/spans resolve, no accepted invented identity/source, and no purpose-policy bypass. Freeze task-specific quality targets before testing; disclose sample limitations rather than claim production accuracy from a small smoke test.

Ask retrieves the same eligible evidence under the selected context. Facts receive citations; interpretations/creative hypotheses are distinguished. Unknown/unavailable states are explicit. No arbitrary SQL/tool execution or unrestricted browsing by the model. Requested mutations become proposals. Source captions/pages cannot inject instructions, retrieve secrets or alter policy.

## Numerical forecasts and experiments

Trajectory forecast asks what may happen under recent conditions, not whether an Instagram action caused streams. Use the actual supported outcome contract. Begin evaluation design and prospective ledger alongside imports. Fit on affected Spotify inputs only after source-use gate; no fine-tuning workaround.

Freeze dataset hash, as-of cutoffs, revisions/availability limitations, development rolling origins and final holdout before comparing recent-history/seasonal-naive baselines with a simple candidate. Report absolute error, bias, interval coverage/width, sparse and regime-change cases. Avoid percentage error where zeros make it invalid. Keep prospective forecasts saved before outcomes arrive. Predeclare acceptance thresholds based on useful baseline improvement and honest uncertainty, then leave the final holdout untouched.

Five active days in the supplied data are insufficient for an independent reliability claim. Preserve zero padding, but do not treat 997 pre-activity days as informative training history or release-date evidence. Peer Bayesian pooling is an optional tested same-metric candidate; the toy beta-binomial POC is not a stream-count model.

Experiments freeze hypothesis/variable/outcome/comparison/windows before running. Mature observations and actual execution produce a reviewed result with confounders. Nonrandomised comparisons cannot claim causal proof. Reviewed learning can affect later recommendations via new findings/rule/model versions; training on it is still subject to permission and independent evaluation.
