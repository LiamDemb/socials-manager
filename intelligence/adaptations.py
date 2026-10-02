import hashlib

from django.db import transaction

from core import clock
from core.errors import DomainError
from core.services import audit, idempotent

from .models import AdaptationProposal


def fingerprint(campaign_id, reason: str, evidence: dict) -> str:
    raw = f"{campaign_id}:{reason}:{sorted(evidence.items())}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def propose(campaign, reason: str, diff: dict, evidence: dict):
    if campaign.status == "paused":
        return None
    fp = fingerprint(campaign.pk, reason, evidence)
    existing = AdaptationProposal.objects.filter(campaign=campaign, fingerprint=fp, state="pending").first()
    if existing:
        return existing
    return AdaptationProposal.objects.create(
        campaign=campaign,
        fingerprint=fp,
        summary=reason[:300],
        diff=diff,
        evidence=evidence,
        base_campaign_revision=campaign.revision,
        created_at=clock.now(),
    )


def _apply_diff(campaign, diff: dict):
    from campaigns.models import Activity
    from catalogue.services import parse_date

    applied = []
    for item in diff.get("activities") or []:
        aid = item.get("activity_id")
        if not aid:
            continue
        activity = Activity.objects.select_for_update().filter(pk=aid, campaign=campaign).first()
        if not activity:
            continue
        if item.get("date"):
            day = parse_date(item["date"], "date")
            activity.all_day_date = day
            activity.planned_at_utc = None
            activity.save(update_fields=["all_day_date", "planned_at_utc"])
            applied.append(str(activity.pk))
        if item.get("title"):
            activity.title = str(item["title"])[:200]
            activity.save(update_fields=["title"])
    return applied


def decide(proposal_id, action: str, key):
    def run():
        prop = AdaptationProposal.objects.select_for_update().select_related("campaign").get(pk=proposal_id)
        if prop.state != "pending":
            raise DomainError("already_decided", "This adaptation was already decided.")
        campaign = prop.campaign
        if campaign.revision != prop.base_campaign_revision:
            raise DomainError("stale_campaign", "Campaign changed since this proposal. Review again.")
        if action == "accept":
            applied = _apply_diff(campaign, prop.diff)
            prop.state = "accepted"
            prop.decided_at = clock.now()
            prop.save(update_fields=["state", "decided_at"])
            audit("adaptation", prop.pk, "accept", {"campaign": str(campaign.pk), "applied": applied})
            return {"state": "accepted", "diff": prop.diff, "applied": applied}
        if action == "reject":
            prop.state = "rejected"
            prop.decided_at = clock.now()
            prop.save(update_fields=["state", "decided_at"])
            audit("adaptation", prop.pk, "reject", {})
            return {"state": "rejected"}
        raise DomainError("invalid_action", "Choose accept or reject.")

    with transaction.atomic():
        return idempotent(key, f"adaptation.{action}:{proposal_id}", run)
