"""Evidence-backed campaign draft generation."""
import json

from core import clock

from . import scheduler, tactics, validation
from .assessments import basis_for_activity
from .composition import rank_and_compose
from .contracts import campaign_phase_type
from .evidence import build_bundle_for_campaign
from .evidence_slices import build_slices_for_tactics
from .llm_adapter import generate_structured
from .models import RecommendationRecord, SchedulingDecision
from .agenda import build_analysis_agenda
from .analysis import AnalysisResolver
from .claims import build_claim_records
from .decision_context import freeze_context
from .needs import derive_campaign_needs
from .planning import resolve_planning_context
from .support import SUPPORT_CREATIVE, SUPPORT_SUPPORTED, support_label_display
from .tactics import TACTIC_CATALOGUE_VERSION


def _phase_for(payload):
    ctx = resolve_planning_context(payload)
    start = ctx["start_date"]
    end = ctx["end_date"]
    key = ctx["key_date"]
    mid = start + (end - start) / 2
    return scheduler.campaign_phase(payload["type"], key, mid, start, end)


def _format_exclusion(tid, reason):
    return f"Tactic {tid} excluded: {reason.replace('_', ' ')}."


def generate_evidence_activities(payload, operational_preview):
    """Return extra content activities, gaps, planning notes, and a draft recommendation record id."""
    ctx = resolve_planning_context(payload)
    primary_metric_id = ctx["primary_metric_id"]
    gaps = [g for g in operational_preview.get("gaps", []) if "No eligible evidence yet" not in g]
    planning_notes = []

    bundle = build_bundle_for_campaign(payload)
    gaps.extend(bundle.get("gaps") or [])

    phase = _phase_for(payload)
    needs = derive_campaign_needs(ctx, bundle, phase=phase)
    planning_notes.extend(needs.get("data_gaps") or [])
    planning_notes.extend(needs.get("needs_rationale") or [])

    from intelligence.peer_dataset import enrich_analysis_ctx

    analysis_ctx = enrich_analysis_ctx(
        {**ctx, "dataset_hash": bundle.get("fingerprint"), "policy_versions": bundle.get("policy_versions") or {}}
    )
    peer_ds = analysis_ctx.get("dataset_meta") or {}
    if peer_ds.get("post_count", 0) == 0 and peer_ds.get("peer_ids"):
        planning_notes.append(
            "Peer posts are collected but lack public metrics at capture for comparable analysis, or cohort is empty."
        )
    agenda = build_analysis_agenda(ctx, needs)
    resolver = AnalysisResolver()
    agenda_results = resolver.resolve_agenda(agenda, analysis_ctx)
    for ar in agenda_results:
        if ar.get("status") == "blocked":
            planning_notes.append(f"Analysis blocked ({ar.get('blocker_code')}): {ar.get('detail')}")
        elif ar.get("status") == "insufficient_data":
            planning_notes.append(f"Analysis insufficient: {ar.get('detail') or ar.get('request', {}).get('analysis_key')}")
    decision = freeze_context(payload, ctx, bundle, needs, agenda_results)

    candidates, rejected = tactics.candidate_tactics(
        payload["type"],
        phase,
        ctx["channels"],
        context=ctx,
    )
    for tid, reason in rejected:
        planning_notes.append(_format_exclusion(tid, reason))

    if not candidates:
        planning_notes.append("No tactics matched campaign type, channels, and phase after hard filtering.")
        meta = {"excluded": [{"tactic_id": t, "reason_code": r, "detail": ""} for t, r in rejected], "needs": needs}
        rec = _store_preview_recommendation(None, payload, bundle, meta)
        return _empty_result(gaps, planning_notes, bundle, rec)

    start = ctx["start_date"]
    end = ctx["end_date"]
    assets = ctx["assets_ready_date"]
    blackouts = ctx["blackout_dates"]
    days = scheduler.feasible_days(start, end, assets, blackouts)
    if not days:
        gaps.append("No feasible days in the campaign window after assets and blackouts.")
        rec = _store_preview_recommendation(None, payload, bundle, {"needs": needs, "rejected": rejected})
        return _empty_result(gaps, planning_notes, bundle, rec)

    slices = build_slices_for_tactics(ctx, candidates)
    selected, composition_meta, schedule_hints = rank_and_compose(
        candidates, ctx, needs, slices, days, budget_minor=ctx.get("budget_minor")
    )
    for d in composition_meta.get("deferred") or []:
        planning_notes.append(f"Tactic {d['tactic_id']} deferred: {d.get('detail') or d.get('reason_code', '').replace('_', ' ')}.")

    tz = ctx["timezone"]
    out = []
    errors = []
    for idx, item in enumerate(selected):
        tactic = item["tactic"]
        strategic = item["strategic_fit"]
        evidence = item["evidence_support"]
        slice_bundle = item["slice_bundle"]
        support = evidence["support_label"]
        support_reason = evidence["support_reason"]
        day = schedule_hints[idx] if idx < len(schedule_hints) else days[min(len(days) - 1, idx * 2)]
        schedule = scheduler.pick_time_slot(
            day, campaign_phase_type(payload["type"]), decision.get("timing_evidence"), tz
        )
        evidence_snippets = [r.get("snippet") or r.get("metric_id", "") for r in (slice_bundle.get("observation_refs") or [])[:4]]
        finding_titles = [f.get("title", "") for f in (slice_bundle.get("finding_refs") or [])[:2]]
        brief_payload = {
            "campaign_type": payload["type"],
            "campaign_name": ctx["campaign_name"],
            "object_label": ctx["object_label"],
            "audience": ctx["audience"],
            "channels": ctx["channels"],
            "tactic_id": tactic["id"],
            "format": tactic["formats"][0],
            "support_label": support,
            "support_reason": support_reason,
            "transfer_limits": tactic["transfer_limits"],
            "evidence_snippets": evidence_snippets,
            "finding_titles": finding_titles,
            "constraints": ctx["constraints"],
            "strategic_role": (strategic.get("roles") or [""])[0],
            "proposition": evidence.get("proposition"),
        }
        llm = generate_structured("activity_brief", brief_payload)
        evidence_ids = [
            r.get("observation_version_id") or r.get("observation_id")
            for r in (slice_bundle.get("observation_refs") or [])[:3]
        ]
        evidence_ids.extend([f.get("finding_id") for f in (slice_bundle.get("finding_refs") or [])[:2]])
        evidence_ids = [e for e in evidence_ids if e]
        kind = "operational" if tactic.get("kind") == "operational" else "content"
        has_refs = bool(slice_bundle.get("observation_refs") or slice_bundle.get("finding_refs"))
        if kind == "content" and support == SUPPORT_SUPPORTED and has_refs:
            draft_kind = "evidence_backed"
        elif kind == "content":
            draft_kind = "planning_hypothesis" if support == SUPPORT_CREATIVE else "transfer_hypothesis"
        else:
            draft_kind = "operational"
        item_errors = validation.validate_activity_draft(
            {
                "kind": draft_kind,
                "channel": tactic["channels"][0],
                "evidence_ids": evidence_ids,
                "email_list_confirmed": ctx.get("email_list_confirmed"),
            },
            {**bundle, **slice_bundle},
        )
        if item_errors and draft_kind == "evidence_backed":
            errors.extend(item_errors)
            gaps.append(f"{tactic['id']}: validation failed ({', '.join(item_errors)}).")
            draft_kind = "planning_hypothesis"
            evidence_ids = []
        basis = basis_for_activity(evidence, schedule.get("basis"))
        role_label = (strategic.get("roles") or ["support"])[0]
        title = f"{ctx['object_label'] or ctx['type_label']}: {tactic['formats'][0]} ({tactic['id'].replace('_', ' ')})"
        claims = build_claim_records(strategic, evidence)
        from intelligence.inspiration_service import recommend_for_preview_fields

        ref_out = recommend_for_preview_fields(
            {
                "channel": tactic["channels"][0],
                "format": tactic["formats"][0],
                "purpose": (needs.get("primary_purpose") or "") if isinstance(needs, dict) else "",
                "roles": [role_label],
                "phase": phase,
            },
            limit=3,
        )
        ref_suggestions = ref_out.get("suggestions") or []
        if ref_out.get("gaps"):
            planning_notes.extend(ref_out["gaps"][:2])
        activity = {
            "template_key": tactic["id"],
            "scheduling_json": json.dumps(schedule),
            "title": title[:200],
            "kind": kind,
            "date": day.isoformat(),
            "time": schedule["chosen_local"][11:16],
            "channel": tactic["channels"][0],
            "format": tactic["formats"][0],
            "purpose": (llm.data or {}).get("brief", "")[:2000],
            "brief": (llm.data or {}).get("brief", "")[:10000],
            "cta": (llm.data or {}).get("cta", "")[:300],
            "effort_minutes": tactic.get("effort_minutes") or 45,
            "origin": "evidence_recommendation",
            "basis": basis,
            "selected": True,
            "evidence_ids": evidence_ids if draft_kind == "evidence_backed" else [],
            "scheduling": schedule,
            "generation": {"backend": llm.backend, "prompt_version": "synthesis-v3", "error": llm.error},
            "provenance": {
                "support": support,
                "support_reason": support_reason,
                "support_display": support_label_display(support),
                "draft_kind": draft_kind,
                "bundle_fingerprint": bundle.get("fingerprint"),
                "finding_refs": slice_bundle.get("finding_refs"),
                "tactic_id": tactic["id"],
                "tactic_catalogue_version": TACTIC_CATALOGUE_VERSION,
                "strategic_fit": strategic,
                "evidence_support": {
                    k: evidence[k]
                    for k in ("proposition", "support_label", "support_reason", "transfer_limits", "coverage_note")
                },
                "role": role_label,
                "supports_outcome_id": strategic.get("supports_outcome_id"),
                "composition_policy": composition_meta.get("composition_policy"),
                "claims": claims,
                "decision_context_fingerprint": decision.get("fingerprint"),
                "reference_suggestions": ref_suggestions,
            },
            "reference_suggestions": ref_suggestions,
            "reference_ids": [],
        }
        out.append(activity)

    if not out and candidates:
        planning_notes.append("No tactics selected after composition; operational checklist may still apply.")

    composition_meta["activities"] = [a["template_key"] for a in out]
    composition_meta["decision_context"] = {
        "fingerprint": decision.get("fingerprint"),
        "agenda_results": [{"status": a.get("status"), "key": a.get("request", {}).get("analysis_key")} for a in agenda_results],
    }
    rec = _store_preview_recommendation(None, payload, bundle, composition_meta)
    for a in out:
        a["recommendation_id"] = str(rec.pk)
    return {
        "activities": out,
        "gaps": gaps,
        "planning_notes": planning_notes,
        "composition": {
            "policy": composition_meta.get("composition_policy"),
            "selected": composition_meta.get("selected"),
            "deferred": composition_meta.get("deferred"),
            "excluded": composition_meta.get("excluded"),
        },
        "bundle": bundle,
        "llm_used": bool(out),
        "validation_errors": errors,
        "recommendation_id": str(rec.pk),
    }


def _empty_result(gaps, planning_notes, bundle, rec):
    return {
        "activities": [],
        "gaps": gaps,
        "planning_notes": planning_notes,
        "composition": {},
        "bundle": bundle,
        "llm_used": False,
        "recommendation_id": str(rec.pk),
    }


def _store_preview_recommendation(campaign_id, payload, bundle, meta):
    from campaigns.services import jsonable_campaign_draft
    from core.jsonutil import jsonable_snapshot

    return RecommendationRecord.objects.create(
        campaign_id=campaign_id,
        kind="campaign_preview",
        state="validated",
        payload={"campaign": jsonable_campaign_draft(payload), "meta": jsonable_snapshot(meta)},
        evidence_bundle=jsonable_snapshot(bundle or {}),
        generation={"prompt_version": "synthesis-v3"},
        validation={"citations_checked": True, "bundle_fingerprint": (bundle or {}).get("fingerprint")},
        created_at=clock.now(),
    )


def attach_recommendation_to_campaign(recommendation_id, campaign_id):
    rec = RecommendationRecord.objects.filter(pk=recommendation_id, state="validated").first()
    if not rec:
        return None
    rec.campaign_id = campaign_id
    rec.state = "accepted"
    rec.save(update_fields=["campaign_id", "state"])
    return rec


def persist_scheduling(activity, schedule: dict):
    version = activity.scheduling_decisions.count() + 1
    return SchedulingDecision.objects.create(
        activity=activity,
        version=version,
        requested_window=schedule.get("requested_window", {}),
        feasible_candidates=schedule.get("feasible_candidates", []),
        chosen_local=schedule["chosen_local"],
        timezone=schedule["timezone"],
        basis=schedule["basis"],
        fallback=schedule.get("fallback", True),
        rule_version=schedule.get("rule_version", "scheduler-v1"),
        evidence_refs=schedule.get("evidence_refs", []),
        created_at=clock.now(),
    )
