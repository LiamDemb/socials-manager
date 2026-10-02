"""Read-only snapshot for Ask. Does not create campaigns, activities or observations.

Owner decision (2 Oct 2026): Ask may send already-stored artist, source, campaign and peer
records to the local model. Campaign synthesis still uses source llm_ingest policy.
"""
from datetime import timedelta

from campaigns.models import Campaign
from catalogue.models import PromotedObject
from catalogue.services import own_artist
from context.models import InspirationReference, PeerProfile
from core import clock
from findings.models import Finding
from sources.models import Observation, Source

from .validation import sanitize_retrieved_text

MAX_FACTS = 80
OBS_PER_SERIES = 8


def _fact(kind, text, source, evidence_id):
    return {
        "evidence_id": str(evidence_id),
        "kind": kind,
        "source": source,
        "text": sanitize_retrieved_text(text, 400),
    }


def build_ask_context():
    facts = []
    gaps = []
    artist = own_artist()
    if artist:
        facts.append(_fact("identity", f"Own artist: {artist.label}", "catalogue", artist.pk))
    else:
        gaps.append("No own artist is configured.")

    for source in Source.objects.filter(state="active"):
        cap = source.capability or {}
        username = cap.get("instagram_username") or (cap.get("profile") or {}).get("username") or cap.get("handle")
        account = cap.get("account")
        if source.provider == "instagram" or username or account:
            handle = account or (f"@{username}" if username else source.label)
            profile = cap.get("profile") or {}
            bits = [f"Instagram connection: {handle}", f"live check {cap.get('live_integration', 'unknown')}"]
            if profile.get("account_type"):
                bits.append(f"account type {profile['account_type']}")
            if profile.get("followers_count") is not None:
                bits.append(f"followers {profile['followers_count']}")
            own = cap.get("own_account") or {}
            if own.get("account_id"):
                bits.append(f"account id {own['account_id']}")
            if cap.get("fields") and isinstance(cap.get("fields"), dict):
                for key in ("followers_count", "media_count", "username"):
                    if cap["fields"].get(key) is not None:
                        bits.append(f"{key} {cap['fields'][key]}")
            facts.append(_fact("instagram", "; ".join(bits), "instagram", source.pk))
            if not cap.get("business_discovery_supported"):
                gaps.append("Peer Business Discovery is not marked available on the stored Instagram capability.")
        else:
            facts.append(
                _fact("source", f"Source {source.label} ({source.provider}/{source.route}) is {source.state}.", source.provider, source.pk)
            )

    cutoff = clock.now().date() - timedelta(days=120)
    series = {}
    qs = (
        Observation.objects.filter(active_version__isnull=False, period_start__gte=cutoff)
        .select_related("entity", "metric", "active_version")
        .order_by("entity_id", "metric_id", "-period_start")
    )
    for obs in qs:
        key = (obs.entity_id, obs.metric_id)
        bucket = series.setdefault(key, [])
        if len(bucket) >= OBS_PER_SERIES:
            continue
        value = obs.active_version.value
        shown = "missing" if value is None else str(value)
        bucket.append(
            _fact(
                "observation",
                f"{obs.entity.label}: {obs.metric.label} on {obs.period_start.isoformat()} = {shown}",
                obs.metric.provider,
                obs.active_version_id,
            )
        )
    for bucket in series.values():
        facts.extend(reversed(bucket))

    if not series:
        gaps.append("No stored observations in the last 120 days.")

    for obj in PromotedObject.objects.select_related("entity").order_by("entity__label")[:30]:
        when = obj.key_date.isoformat() if obj.key_date else "no key date"
        facts.append(
            _fact(
                "catalogue",
                f"{obj.get_kind_display()} {obj.entity.label}, key date {when}, identity {obj.identity_state}.",
                "catalogue",
                obj.pk,
            )
        )

    from intelligence.models import RecommendationRecord

    for campaign in Campaign.objects.order_by("-start_date")[:15]:
        facts.append(
            _fact(
                "campaign",
                f"Campaign {campaign.name} ({campaign.type}, {campaign.status}) {campaign.start_date.isoformat()} to {campaign.end_date.isoformat()}.",
                "campaigns",
                campaign.pk,
            )
        )
        rec = RecommendationRecord.objects.filter(campaign=campaign).order_by("-created_at").first()
        if not rec:
            rec = RecommendationRecord.objects.filter(
                state="validated", payload__campaign__name=campaign.name
            ).order_by("-created_at").first()
        if rec and isinstance(rec.payload, dict):
            meta = (rec.payload or {}).get("meta") or {}
            for sel in meta.get("selected") or []:
                tid = sel.get("tactic_id", "")
                sf = sel.get("strategic_fit") or {}
                es = sel.get("evidence_support") or {}
                facts.append(
                    _fact(
                        "planning_decision",
                        f"Campaign {campaign.name}: selected tactic {tid}. Role(s) {', '.join(sf.get('roles') or [])}. "
                        f"{es.get('support_reason') or sf.get('rationale', '')}",
                        "intelligence",
                        rec.pk,
                    )
                )
            for item in (meta.get("deferred") or [])[:5]:
                facts.append(
                    _fact(
                        "planning_decision",
                        f"Campaign {campaign.name}: deferred tactic {item.get('tactic_id')}: {item.get('detail') or item.get('reason_code')}.",
                        "intelligence",
                        rec.pk,
                    )
                )
            for item in (meta.get("excluded") or [])[:5]:
                facts.append(
                    _fact(
                        "planning_decision",
                        f"Campaign {campaign.name}: excluded tactic {item.get('tactic_id')}: {item.get('reason_code')}.",
                        "intelligence",
                        rec.pk,
                    )
                )

    for finding in Finding.objects.filter(status="published").order_by("-computed_at")[:10]:
        facts.append(_fact("finding", f"Finding: {finding.title}. {finding.summary[:240]}", "findings", finding.pk))

    for peer in PeerProfile.objects.order_by("label")[:25]:
        handle = f"@{peer.instagram_username}" if peer.instagram_username else "no Instagram handle"
        facts.append(
            _fact(
                "peer",
                f"Peer {peer.label} ({peer.review_state}), {handle}. Similarity is a discovery signal, not campaign effectiveness.",
                "peers",
                peer.pk,
            )
        )

    for ref in InspirationReference.objects.order_by("-retrieved_at")[:10]:
        facts.append(
            _fact("inspiration", f"Inspiration: {ref.title}. {sanitize_retrieved_text(ref.excerpt, 180)}", "inspiration", ref.pk)
        )

    facts = facts[:MAX_FACTS]
    return {
        "facts": facts,
        "gaps": gaps,
        "read_only": True,
        "note": "Ask context only. No campaigns, activities or source records are created from this snapshot.",
    }
