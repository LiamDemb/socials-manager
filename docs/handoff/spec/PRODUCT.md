# Product specification

## Purpose

Band Evidence helps an artist/team decide what to do next using collected data. It builds and runs practical campaigns, makes recommendations inspectable, measures compatible outcomes and retains what was learned. The loop is data → evidence → finding → recommendation → approved campaign → execution → measurement → learning. The user remains the decision maker.

For a release, create the strongest supportable campaign within the artist's resources. For ongoing growth, turn a measurable objective into executable work. For a show, tie promotion and results to the event rather than forcing release terminology. Efficient, honest decisions matter more than a large dashboard or volume of AI suggestions.

## Domain objects

| Object | Definition and responsibility |
| --- | --- |
| Artist | Canonical own band or reviewed peer. Same identity model, different available observations. Installation configuration points to one own artist. |
| Promoted object | Recording, release/track set, event, video or merch item with local identity, dates and verified external mappings. May be pending before an external identifier exists. |
| Campaign (Plan) | Time-bounded strategy/execution container: type, object, key dates, audience, resources, linked outcomes, activities, decisions and revisions. |
| Outcome (Goal) | Versioned measurable success contract: metric/scope/unit, baseline, target semantics, window, timezone and coverage. Reusable across campaigns. |
| Activity | One thing to make/do: execution brief, channel/format, planned time, actual execution, outcome links, evidence, references and history. One stable identity. |
| Experiment | Optional approved protocol addressing a specific uncertainty over actual activities, comparison and measurement windows. |
| Observation | Original measured value with metric definition, entity/window, observation and availability time, source/row and revision. |
| Evidence bundle | Frozen eligible observation/interpretation/cohort versions for a specific purpose and cutoff. Evidence is scoped, not a generic pile of documents. |
| Finding | Versioned descriptive/statistical interpretation of eligible evidence, with method, sample, uncertainty and limitations. |
| Recommendation | Reviewable proposal with evidence, rationale, assumptions, constraints, support, proposed work/diff and decision. |
| Inspiration | Purpose-matched creative example with source, reviewed context, observable limits and preference state. Saving it does not establish effectiveness. |
| Source | Provider/account, imported file or external page with origin, capabilities, use/retention rules, coverage, freshness and failures. |
| Peer | Verified comparator with inclusion state, relevance dimensions, observations and references. Similarity is not automatic transferability. |
| Learning record | Reviewed interpretation of outcome/experiment results and next decision. Separate from raw measurements and preference feedback. |

`CampaignOutcome` and `ActivityOutcome` are links, not copies. Recording/release relations allow the same recording on several releases. Campaigns can share a promoted object. A shared follower outcome has one baseline/window and one progress calculation. Two genuinely different windows or scopes are separate contracts.

## Navigation

| Destination | User question | Responsibilities |
| --- | --- | --- |
| Today | What is moving and what needs attention? | Artist-wide movement, source freshness, due/overdue work, upcoming moments, campaign and deduplicated outcome summaries, few useful alerts. Each alert opens its named campaign/activity/source. |
| Campaigns | What are we trying to achieve and what should we do? | Create/open campaign; Calendar, Strategy, Outcomes, Learning; aggregate outcome report. |
| Inspiration | What references could help? | Browse/filter/save reviewed examples; use a reference in an activity brief. |
| Evidence | What do we know and how reliable is it? | Fixed Findings / Observed data / Review context tabs, observations and reproducible derivations. |
| Peers | Who is a relevant comparator? | Identity/relevance, observability, include/exclude/pin, behaviour and references feeding evidence. |
| Sources | Where does our information come from? | Connections, imports, capabilities, coverage, errors, original/re-exported files and external provenance. |
| Ask | Help me interpret this context | Grounded questions, citations, navigation and reviewable proposals. Same evidence/purpose gates as the rest of the app. |

Settings is secondary for artist, timezone, practical defaults, backup/export and model status. No prominent logo, repeated title, opaque plan selector or tenant switcher. Plan-specific “keep moving” work lives in its campaign. Today does not operate an unnamed plan or goal.

## Campaign scope and creation

Types: single, EP/album, live show, tour announcement, music video, merch launch, audience growth, content push, other. Use one extensible type registry with conditional important fields, not a form containing all possible fields.

1. **Purpose:** type, known/pending object, dates and primary outcome. Reuse catalogue facts; changes to a known date are explicit. Growth has no irrelevant release object/date. Optional supporting outcomes are progressively added.
2. **Resources:** only information that changes recommendations: existing channels/account, audience/region, assets and ready dates, total capacity, budget ceiling, availability/blackouts and constraints. Email requires an authorised opted-in list; show needs venue/date/ticket destination or source setup.
3. **Review proposed campaign:** concise dated cards and gaps; reason/creative detail on demand, select/edit/move/remove/add, validate then approve. Approval creates only selected activities. A pending model job never traps the form.

Do not promise a filled marketing campaign without eligible evidence for performance claims. Generate operational setup/milestones from user dates and dependencies. Tactics may be proposed for strategic fit when observable metrics differ from the primary outcome (ADR 0004); label support honestly. Allow manual activities and identify data gaps. A creative template can help the user write a manually chosen activity without claiming empirical backing.

## Activity execution content

Core view: title/purpose, date/time and compact Timing link, channel/format, concept, creative brief, caption/headline direction when relevant, CTA, asset readiness, concise references, execution state and controls. Secondary: Why this activity?, full evidence/source drill-down, assumptions/support, experiment protocol and audit history. A non-content task uses an operational checklist, not irrelevant captions.

The brief must answer what to make and do. Editing preserves original recommendation/evidence provenance and marks changed rationale where applicable. References are contextual by objective, purpose, format, phase and permitted observable result; unmatched cases say no reviewed match rather than showing random examples.

## State model

Campaign: Draft → Active ↔ Paused → Completed / Cancelled. Terminal campaigns retain records; prompts/adaptations pause. Reactivation is explicit and audited.

Activity persisted execution state: Planned, Completed, Skipped, Cancelled. Planned with no date is Unscheduled. For active work, display Overdue if scheduled timestamp has passed; Due today if later today; Upcoming otherwise. All-day work becomes overdue after the due local day. Completed/Skipped/Cancelled override clock-derived labels. Paused/terminal campaign items remain visible in history without active prompts.

Completion stores actual timestamp, optional published URL and notes; actual time cannot be future. Skip/cancel requires a reason. Reopen appends history. No measurement or outcome progress is inferred from completion. A completed item cannot be dragged without deliberate reopen. Changing campaign/object dates flags affected approved work rather than moving it silently.

Outcome: source-backed progress with coverage/freshness, Met/Not met only when the contract can be evaluated, otherwise Unknown/Partial. Window ended with missing data is not automatic failure. Linear pacing is a guide, not a validated forecast.

Recommendation: Draft → Validated → Accepted / Rejected / Superseded; Stale or Blocked may prevent approval. Experiments: Draft → Approved → Running → Awaiting measurement → Reviewed / Abandoned. Approved protocol changes require a new version/review.

## Adaptation and learning

New comparable results, changed progress/coverage, overdue work, corrected context, changed resource constraints or key dates can trigger recomputation. It produces a reasoned diff, never a silent mutation. Show what changed, inputs/limits and proposed adjustment; accept/modify/reject transactionally. Cooldown/fingerprints suppress repeated suggestions from identical evidence. Acceptance is not measured success; rejection is preference feedback.

Learning uses actual execution and compatible observations; optional experiments make uncertainties explicit. Confounders include paid activity, press, playlists, concurrent posts/releases and changing audience. The system can say inconclusive. Learning may change a later finding/ranking only through versioned, eligible inputs and evaluated rules/models.
