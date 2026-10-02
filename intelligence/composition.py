"""Deterministic ranking and set-based campaign composition."""
from core import instance

from .assessments import assess_evidence_support, assess_strategic_fit
from .evidence_slices import merge_slice_for_tactic
from .support import SUPPORT_CREATIVE, SUPPORT_OPERATIONAL, SUPPORT_SUPPORTED, SUPPORT_TRANSFER
from .tactics import TACTIC_CATALOGUE_VERSION

COMPOSITION_POLICY_VERSION = "compose-v1"
MAX_SELECTED = 4
MIN_SELECTED = 1

_SUPPORT_SCORE = {
    SUPPORT_SUPPORTED: 25,
    SUPPORT_TRANSFER: 15,
    SUPPORT_OPERATIONAL: 20,
    SUPPORT_CREATIVE: 5,
    "no_empirical_support": 0,
}


def _rank_score(tactic, strategic, evidence, needs):
    priorities = needs.get("role_priorities") or []
    roles = tactic.get("roles") or []
    role_bonus = 0
    for r in roles:
        if r in priorities:
            role_bonus = max(role_bonus, 30 - priorities.index(r) * 5)
    strat_bonus = 20 if strategic.get("prerequisites_met") else -100
    ev_bonus = _SUPPORT_SCORE.get(evidence.get("support_label"), 0)
    effort = tactic.get("effort_minutes") or 45
    effort_bonus = max(0, 10 - effort // 10)
    return role_bonus + strat_bonus + ev_bonus + effort_bonus


def rank_candidates(candidates, ctx, needs, slices, assessments_out: list):
    ranked = []
    for tactic in candidates:
        strategic = assess_strategic_fit(tactic, ctx, needs)
        if not strategic.get("prerequisites_met"):
            assessments_out.append(
                {
                    "tactic_id": tactic["id"],
                    "strategic_fit": strategic,
                    "excluded": True,
                    "reason_code": "prerequisites_unmet",
                }
            )
            continue
        slice_bundle = merge_slice_for_tactic(tactic, slices)
        evidence = assess_evidence_support(tactic, ctx, slice_bundle)
        score = _rank_score(tactic, strategic, evidence, needs)
        ranked.append(
            {
                "tactic": tactic,
                "strategic_fit": strategic,
                "evidence_support": evidence,
                "score": score,
                "slice_bundle": slice_bundle,
            }
        )
        assessments_out.append(
            {
                "tactic_id": tactic["id"],
                "strategic_fit": strategic,
                "evidence_support": evidence,
                "score": score,
            }
        )
    ranked.sort(key=lambda x: (-x["score"], x["tactic"]["id"]))
    return ranked


def _similar(a, b):
    return a["tactic"]["channels"][0] == b["tactic"]["channels"][0] and a["tactic"]["formats"][0] == b["tactic"]["formats"][0]


def _role_coverage_ok(selected, needs):
    priorities = (needs.get("role_priorities") or [])[:3]
    covered = set()
    for item in selected:
        covered.update(item["tactic"].get("roles") or [])
    return any(r in covered for r in priorities)


def rank_and_compose(candidates, ctx, needs, slices, days: list, budget_minor=None):
    assessments_log = []
    ranked = rank_candidates(candidates, ctx, needs, slices, assessments_log)
    excluded = [{"tactic_id": a["tactic_id"], "reason_code": a.get("reason_code", "prerequisites_unmet"), "detail": ""} for a in assessments_log if a.get("excluded")]
    deferred = []
    selected = []
    used_effort = 0
    limit = instance.load().get("weekly_capacity_minutes") or 600

    for item in ranked:
        if len(selected) >= MAX_SELECTED:
            deferred.append({"tactic_id": item["tactic"]["id"], "reason_code": "capacity_slot_full", "detail": "Composition limit reached."})
            continue
        if any(_similar(item, s) for s in selected):
            deferred.append({"tactic_id": item["tactic"]["id"], "reason_code": "duplicate_format", "detail": "Similar channel/format already selected."})
            continue
        effort = item["tactic"].get("effort_minutes") or 45
        if budget_minor is not None and used_effort + effort > budget_minor:
            deferred.append({"tactic_id": item["tactic"]["id"], "reason_code": "budget_exceeded", "detail": "Would exceed stated budget effort."})
            continue
        if used_effort + effort > limit and selected:
            deferred.append({"tactic_id": item["tactic"]["id"], "reason_code": "workload_deferred", "detail": "Deferred to respect weekly labour heuristic."})
            continue
        selected.append(item)
        used_effort += effort

    if selected and not _role_coverage_ok(selected, needs):
        for item in ranked:
            if item in selected:
                continue
            if any(_similar(item, s) for s in selected):
                continue
            if set(item["tactic"].get("roles") or []) & set((needs.get("role_priorities") or [])[:2]):
                if len(selected) < MAX_SELECTED:
                    selected.append(item)
                    break

    if not selected and ranked:
        selected = [ranked[0]]

    meta = {
        "composition_policy": COMPOSITION_POLICY_VERSION,
        "tactic_catalogue_version": TACTIC_CATALOGUE_VERSION,
        "needs": needs,
        "selected": [
            {
                "tactic_id": s["tactic"]["id"],
                "strategic_fit": s["strategic_fit"],
                "evidence_support": {
                    k: s["evidence_support"][k]
                    for k in ("proposition", "support_label", "support_reason", "transfer_limits", "coverage_note")
                },
                "score": s["score"],
            }
            for s in selected
        ],
        "excluded": excluded,
        "deferred": deferred,
        "assessments": assessments_log,
    }
    schedule_hints = [days[min(len(days) - 1, i * 2)] for i in range(len(selected))]
    return selected, meta, schedule_hints
