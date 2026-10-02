"""Idempotent source collection jobs. Collect outside transactions; commit observations atomically."""
from django.db import transaction

from core import clock
from core.services import audit

from . import instagram
from .models import Source


def run_collect(job):
    source = Source.objects.get(provider=job.scope_key.split(":")[0], route=job.scope_key.split(":")[1])
    cursor = job.cursor or {}
    if source.provider == instagram.IG_PROVIDER:
        report = instagram.probe_live()
        source.capability = {**source.capability, "last_collect": report}
        source.save(update_fields=["capability", "revision"])
        if report["live_integration"] != "Passed":
            audit("source", source.pk, "collect.blocked", {"state": report["live_integration"]}, actor="system")
            return {"state": "blocked", "report": report}
        # Live Graph pagination would continue from cursor["after"] here.
        cursor["after"] = cursor.get("after")
        return {"state": "noop", "cursor": cursor}
    raise RuntimeError(f"Unknown collect scope {job.scope_key}")


@transaction.atomic
def commit_collect(source, payload):
    audit("source", source.pk, "collect.commit", {"payload_keys": list(payload.keys())}, actor="system")
