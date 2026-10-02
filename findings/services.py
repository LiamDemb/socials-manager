"""Reproducible findings from compatible observations. No claim without lineage."""
from django.db import transaction

from core import clock
from core.services import audit

from .models import EvidenceBundle, Finding


def invalidate_for_event(kind, payload):
    """Mark affected published findings superseded when underlying evidence changes."""
    if kind not in ("import.committed", "import.undone", "observation.revised"):
        return []
    touched = []
    for f in Finding.objects.filter(status="published"):
        if f.lineage.get("invalidates_on") == kind:
            f.status = "superseded"
            f.save(update_fields=["status"])
            touched.append(str(f.pk))
    if touched:
        audit("findings", "catalogue", "invalidate", {"kind": kind, "findings": touched}, actor="system")
    return touched


def publish_window_comparison(entity, metric_id, title, summary, window_start, window_end, observation_refs, method_version="window-compare-v1"):
    with transaction.atomic():
        finding = Finding.objects.create(
            title=title,
            summary=summary,
            method_version=method_version,
            status="published",
            entity=entity,
            metric_id=metric_id,
            comparison={"window_start": str(window_start), "window_end": str(window_end)},
            lineage={"invalidates_on": "import.undone", "observation_refs": observation_refs},
            computed_at=clock.now(),
        )
        EvidenceBundle.objects.create(
            finding=finding,
            version=1,
            observation_refs=observation_refs,
            window_start=window_start,
            window_end=window_end,
            created_at=clock.now(),
        )
        audit("finding", finding.pk, "publish", {"metric_id": metric_id})
        return finding
