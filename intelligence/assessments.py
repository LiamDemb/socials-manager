"""Strategic fit and evidence support assessments (deterministic, separate)."""
from .tactics import tactic_observable_metrics
from .support import (
    MIN_INDEPENDENT_UNITS,
    SUPPORT_CREATIVE,
    SUPPORT_OPERATIONAL,
    SUPPORT_SUPPORTED,
    SUPPORT_TRANSFER,
    support_label_display,
)

NO_EMPIRICAL = "no_empirical_support"


def assess_strategic_fit(tactic: dict, ctx: dict, needs: dict) -> dict:
    priorities = needs.get("role_priorities") or []
    roles = tactic.get("roles") or []
    role_rank = min((priorities.index(r) if r in priorities else 99 for r in roles), default=99)
    contribution = tactic.get("contribution") or {}
    supports_id = ctx.get("primary_metric_id") or ""
    if contribution.get("supports_primary") and ctx.get("supporting_metric_ids"):
        for sid in ctx["supporting_metric_ids"]:
            if sid in tactic_observable_metrics(tactic):
                supports_id = sid
                break
    prerequisites_met = True
    limitations = [tactic.get("transfer_limits") or ""]
    if tactic.get("requires_email_list") and not ctx.get("email_list_confirmed"):
        prerequisites_met = False
    if tactic.get("requires_assets") and ctx.get("assets_ready_date") and ctx.get("start_date"):
        if ctx["assets_ready_date"] > ctx["start_date"]:
            prerequisites_met = False
    rationale_parts = [contribution.get("hypothesis") or ""]
    if role_rank < 3:
        rationale_parts.append(f"Fits current priority role ({roles[0] if roles else 'support'}).")
    return {
        "roles": roles,
        "supports_outcome_id": supports_id,
        "rationale": " ".join(p for p in rationale_parts if p).strip(),
        "prerequisites_met": prerequisites_met,
        "limitations": [x for x in limitations if x],
        "role_priority_index": role_rank,
    }


def assess_evidence_support(tactic: dict, ctx: dict, slice_bundle: dict) -> dict:
    from .tactics import tactic_observable_metrics

    observable = set(tactic_observable_metrics(tactic))
    finding_refs = [f for f in (slice_bundle.get("finding_refs") or []) if f.get("metric_id") in observable]
    observation_refs = [r for r in (slice_bundle.get("observation_refs") or []) if r.get("metric_id") in observable]
    primary = ctx.get("primary_metric_id") or ""

    if tactic.get("kind") == "operational":
        return {
            "proposition": "Operational task; not an observed content performance claim.",
            "refs": {"observation_refs": [], "finding_refs": []},
            "support_label": SUPPORT_OPERATIONAL,
            "support_reason": "Operational follow-up, not an observed tactic effect.",
            "transfer_limits": tactic.get("transfer_limits") or "",
            "coverage_note": "",
        }

    matched_metrics = {r.get("metric_id") for r in observation_refs} | {f.get("metric_id") for f in finding_refs}
    matched_metrics.discard(None)

    if primary in observable and primary in matched_metrics:
        if finding_refs:
            proposition = f"Published finding on {primary} (tactic-observable metric)."
            label, reason = SUPPORT_SUPPORTED, "Published finding on an observable metric for this tactic."
        elif len(observation_refs) >= MIN_INDEPENDENT_UNITS:
            proposition = f"Observations on {primary}; association does not prove campaign uplift."
            label, reason = SUPPORT_TRANSFER, "Observations on the observable metric; association does not prove uplift."
        elif observation_refs:
            proposition = f"Limited observations on {primary}."
            label, reason = SUPPORT_TRANSFER, "Limited observations; treat performance link as a hypothesis."
        else:
            proposition = f"No empirical observations for tactic metrics ({', '.join(sorted(observable))})."
            label, reason = SUPPORT_CREATIVE, "No eligible observations for this tactic's observable metrics."
    elif matched_metrics:
        prop_metric = sorted(matched_metrics)[0]
        proposition = (
            f"Evidence supports claims about {prop_metric}, not automatic proof of {primary or 'the primary outcome'}."
        )
        if finding_refs:
            label, reason = SUPPORT_SUPPORTED, f"Finding on {prop_metric}; transfer to primary outcome is not established."
        else:
            label, reason = SUPPORT_TRANSFER, tactic.get("transfer_limits") or "Observable metric differs from primary outcome."
    else:
        proposition = "No empirical support in scope for this tactic's observable metrics."
        label, reason = SUPPORT_CREATIVE, "Planning hypothesis without in-scope observations or findings."

    return {
        "proposition": proposition,
        "refs": {"observation_refs": observation_refs[:6], "finding_refs": finding_refs[:4]},
        "support_label": label,
        "support_reason": reason,
        "transfer_limits": tactic.get("transfer_limits") or "",
        "coverage_note": f"{len(observation_refs)} observation(s), {len(finding_refs)} finding(s) on observable metrics.",
    }


def basis_for_activity(evidence_support: dict, schedule_basis: str) -> str:
    label = evidence_support.get("support_label") or SUPPORT_CREATIVE
    if label == SUPPORT_OPERATIONAL:
        return schedule_basis or "Campaign constraint"
    if label == SUPPORT_SUPPORTED:
        return "Own history"
    if label == SUPPORT_TRANSFER:
        return "Transfer hypothesis"
    return support_label_display(label)
