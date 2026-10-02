from django.db import transaction

from core import clock
from core.services import audit

from sources import lastfm, meta_graph, musicbrainz

from .models import InspirationReference, PeerCandidate, PeerCollectionEntry, PeerProfile, ReviewedContextItem

MAX_CURATED_PEERS = 50


def ensure_default_peers():
    """Tests only: synthetic fixture peer."""
    if PeerProfile.objects.exists():
        return
    PeerProfile.objects.create(
        handle="example_peer",
        label="Example peer (fixture)",
        review_state="reviewed",
        notes="Synthetic fixture peer for tests.",
        capability={"route": "fixture", "live_collection": "blocked"},
        created_at=clock.now(),
        reviewed_at=clock.now(),
    )


def discover_lastfm_similar(seed_artist, limit=30):
    result = lastfm_get_similar(seed_artist, limit)
    created = 0
    for item in result.get("similar", []):
        _, was_new = PeerCandidate.objects.get_or_create(
            source="lastfm",
            name=item["name"],
            defaults={
                "lastfm_url": item.get("url") or "",
                "lastfm_mbid": item.get("mbid") or "",
                "match_score": item.get("match"),
                "provenance": {"seed": seed_artist, "cache_note": item.get("discovery_note")},
                "created_at": clock.now(),
            },
        )
        if was_new:
            created += 1
    audit("peers", "discovery", "lastfm", {"seed": seed_artist, "created": created})
    return {**result, "candidates_created": created}


def lastfm_get_similar(name, limit):
    return lastfm.artist_get_similar(name, limit=limit)


def musicbrainz_search_for_candidate(candidate_id):
    c = PeerCandidate.objects.get(pk=candidate_id)
    return musicbrainz.search_artists(c.name)


@transaction.atomic
def promote_candidate(candidate_id, instagram_username="", musicbrainz_mbid="", notes=""):
    """Human confirmation required. Never infer Instagram from name alone."""
    c = PeerCandidate.objects.select_for_update().get(pk=candidate_id)
    if c.review_state == "rejected":
        raise ValueError("Candidate was rejected.")
    if PeerProfile.objects.filter(label=c.name, review_state="reviewed").exists():
        raise ValueError("Peer already exists.")
    if PeerProfile.objects.filter(review_state="reviewed").count() >= MAX_CURATED_PEERS:
        raise ValueError(f"Curated peer limit ({MAX_CURATED_PEERS}) reached.")
    peer = PeerProfile.objects.create(
        label=c.name,
        lastfm_name=c.name,
        instagram_username=(instagram_username or "").strip().lstrip("@"),
        musicbrainz_artist_id=musicbrainz_mbid or c.musicbrainz_mbid or "",
        handle=(instagram_username or "").strip().lstrip("@"),
        review_state="reviewed",
        notes=notes or c.notes,
        capability={"discovery": c.source, "live_collection": "queued"},
        collection_health={"state": "queued"},
        created_at=clock.now(),
        reviewed_at=clock.now(),
        candidate=c,
    )
    c.review_state = "approved"
    c.reviewed_at = clock.now()
    c.save(update_fields=["review_state", "reviewed_at"])
    PeerCollectionEntry.objects.create(peer=peer, state="queued", updated_at=clock.now(), created_at=clock.now())
    audit("peer", peer.pk, "promote", {"candidate": str(c.pk), "instagram": bool(instagram_username)})
    return peer


def reject_candidate(candidate_id, reason=""):
    c = PeerCandidate.objects.get(pk=candidate_id)
    c.review_state = "rejected"
    c.notes = reason
    c.reviewed_at = clock.now()
    c.save(update_fields=["review_state", "notes", "reviewed_at"])
    return c


def run_peer_collection_batch(limit=3):
    """Rate-aware resumable peer public metric collection via Business Discovery."""
    entries = (
        PeerCollectionEntry.objects.select_related("peer")
        .filter(state__in=["queued", "failed"], peer__review_state="reviewed", peer__instagram_username__gt="")
        .order_by("updated_at")[:limit]
    )
    results = []
    for entry in entries:
        entry.state = "collecting"
        entry.attempts += 1
        entry.updated_at = clock.now()
        entry.save(update_fields=["state", "attempts", "updated_at"])
        username = entry.peer.instagram_username
        snap = meta_graph.business_discovery(username)
        entry.last_snapshot = snap
        if snap["state"] == "ok":
            entry.state = "ok"
            entry.last_error = ""
            entry.peer.collection_health = {"state": "ok", "at": clock.now().isoformat(), "fields": list(snap.get("fields", {}).keys())}
        elif snap["state"] == "blocked":
            entry.state = "blocked"
            entry.last_error = snap.get("reason", "")[:300]
            entry.peer.collection_health = {"state": "blocked"}
        else:
            entry.state = "unavailable" if snap["state"] == "unavailable" else "failed"
            entry.last_error = (snap.get("error") or snap.get("reason") or "")[:300]
            entry.peer.collection_health = {"state": entry.state}
        entry.updated_at = clock.now()
        entry.save()
        entry.peer.save(update_fields=["collection_health"])
        results.append({"peer": entry.peer.label, "state": entry.state})
    return results


def add_inspiration(title, url="", excerpt="", scope="global", scope_ref=""):
    ref = InspirationReference.objects.create(
        scope=scope,
        scope_ref=scope_ref,
        title=title,
        url=url,
        excerpt=excerpt,
        retrieved_at=clock.now(),
    )
    audit("inspiration", ref.pk, "attach", {"scope": scope})
    return ref
