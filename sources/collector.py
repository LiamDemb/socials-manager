"""Idempotent source collection jobs. Collect outside transactions; commit observations atomically."""
from django.db import transaction

from core import clock
from core.services import audit

from context.services import run_peer_collection_batch

from . import instagram, meta_graph
from .models import Source


def run_collect(job):
    scope = job.scope_key
    if scope == "instagram:graph_api":
        return _collect_instagram(job)
    if scope == "peers:business_discovery":
        return _collect_peers(job)
    provider, route = scope.split(":", 1)
    source = Source.objects.get(provider=provider, route=route)
    raise RuntimeError(f"Unknown collect scope {job.scope_key}")


def _collect_instagram(job):
    source = Source.objects.get(provider=instagram.IG_PROVIDER, route=instagram.IG_ROUTE)
    report = instagram.probe_live()
    source.capability = {**source.capability, "last_collect": report, "collected_at": clock.now().isoformat()}
    source.save(update_fields=["capability", "revision"])
    if report["live_integration"] != "Passed":
        audit("source", source.pk, "collect.blocked", {"state": report["live_integration"]}, actor="system")
        return {"state": "blocked", "report": report}
    own = meta_graph.fetch_own_account()
    audit("source", source.pk, "collect.own_account", {"state": own.get("state")}, actor="system")
    return {"state": "ok", "own_account": own.get("state"), "cursor": job.cursor or {}}


def _collect_peers(job):
    cursor = job.cursor or {}
    offset = int(cursor.get("offset", 0))
    batch = run_peer_collection_batch(limit=3)
    cursor["offset"] = offset + len(batch)
    cursor["last_batch"] = batch
    audit("peers", "collection", "batch", {"batch": batch}, actor="system")
    return {"state": "ok", "cursor": cursor, "processed": batch}


@transaction.atomic
def commit_collect(source, payload):
    audit("source", source.pk, "collect.commit", {"payload_keys": list(payload.keys())}, actor="system")
