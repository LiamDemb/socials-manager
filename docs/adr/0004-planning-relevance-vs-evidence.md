# ADR 0004: Planning relevance vs evidence compatibility

**Status:** Accepted (2 Oct 2026)  
**Supersedes:** Primary-outcome metric matching as a **tactic selection** gate (repair-era `metric_mismatch` in `eligible_tactics`).  
**Does not change:** Strict metric IDs for observations, findings, outcome progress, and citation validation.

## Context

Campaigns often combine activities whose **observable** metrics differ from the **primary outcome** (e.g. discovery Reels while measuring follower gain, or Stories while measuring streams). Excluding tactics solely because `outcome_metrics` did not overlap the primary metric produced empty or misleading previews.

## Decision

Separate two decisions:

1. **Planning relevance** — Could this tactic contribute given purpose, phase, channels, prerequisites, and derived strategic role priorities? Implemented in `intelligence/tactics.candidate_tactics`, `intelligence/needs.py`, `intelligence/assessments.assess_strategic_fit`, and `intelligence/composition.rank_and_compose` (`compose-v1`).
2. **Evidence compatibility** — What may observations and findings legitimately support for a proposition? Strict `metric_id` filtering in `intelligence/evidence_slices.py` and `assess_evidence_support`; `metric_ids_match` in `intelligence/contracts.py` remains for analysis compatibility only.

Activities may be proposed as **planning hypotheses** or **transfer hypotheses** without empirical backing. The product must not label them `evidence_backed` without valid refs on the stated proposition.

## Catalogue

`TACTIC_CATALOGUE_VERSION = tactics-v3`: roles, contribution hypotheses, observable metrics, prerequisites, composition hints (`pairs_with`).

## Ranking policy (engineering, not calibrated truth)

Documented weights in `intelligence/composition.py`: role priority match, prerequisites, evidence support ordinal, effort heuristic. LLM narrates selected tactics only; it does not choose the final set or invent scores.

## Consequences

- Preview may show IG Stories on streams-primary releases with honest basis labels.
- Ask and Strategy tab can cite stored `RecommendationRecord.payload.meta` selection/deferral reasons.
- Historical repair docs that implied strict metric matching for selection are superseded for that purpose only.
