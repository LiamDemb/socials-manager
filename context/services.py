from django.db import transaction

from core import clock
from core.services import audit

from sources import lastfm, meta_graph, musicbrainz

from .models import InspirationReference, PeerCandidate, PeerCollectionEntry, PeerMedia, PeerProfile, ReviewedContextItem

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


def _coverage_report(peer, entry):
    collected = peer.media.count()
    reported = (entry.last_snapshot or {}).get("fields", {}).get("media_count")
    if reported is None and isinstance(entry.last_snapshot, dict):
        reported = entry.last_snapshot.get("media_count_reported")
    frac = None
    if reported and int(reported) > 0:
        frac = round(collected / int(reported), 3)
    return {
        "collected_posts": collected,
        "reported_media_count": reported,
        "coverage_fraction": frac,
        "cursor": entry.cursor,
        "last_error": entry.last_error,
        "state": entry.state,
    }


def run_peer_collection_batch(limit=3):
    """Rate-aware resumable peer public metric and media collection via Business Discovery."""
    entries = (
        PeerCollectionEntry.objects.select_related("peer")
        .filter(state__in=["queued", "failed", "ok"], peer__review_state="reviewed", peer__instagram_username__gt="")
        .exclude(state="blocked")
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
        entry.last_snapshot = {**(snap if isinstance(snap, dict) else {}), "profile": snap}
        if snap.get("state") == "ok":
            after = (entry.cursor or {}).get("media_after")
            page = meta_graph.business_discovery_media(username, after=after)
            stored = 0
            if page.get("state") == "ok":
                for item in page.get("items") or []:
                    ext = str(item.get("id") or "")
                    if not ext:
                        continue
                    PeerMedia.objects.update_or_create(
                        peer=entry.peer,
                        external_id=ext,
                        defaults={
                            "permalink": item.get("permalink") or "",
                            "caption": (item.get("caption") or "")[:8000],
                            "media_type": item.get("media_type") or "",
                            "published_at": item.get("timestamp"),
                            "snapshot": item,
                            "collected_at": clock.now(),
                        },
                    )
                    stored += 1
                entry.cursor = {"media_after": page.get("next_after")}
                if not page.get("next_after"):
                    entry.state = "ok"
                else:
                    entry.state = "queued"
            elif page.get("state") == "blocked":
                entry.state = "blocked"
                entry.last_error = page.get("reason", "")[:300]
            else:
                entry.state = "failed"
                entry.last_error = (page.get("error") or "")[:300]
            entry.last_error = entry.last_error or ""
            cov = _coverage_report(entry.peer, entry)
            entry.peer.collection_health = {
                "state": entry.state,
                "at": clock.now().isoformat(),
                "coverage": cov,
                "last_page_stored": stored,
            }
        elif snap.get("state") == "blocked":
            entry.state = "blocked"
            entry.last_error = snap.get("reason", "")[:300]
            entry.peer.collection_health = {"state": "blocked", "coverage": _coverage_report(entry.peer, entry)}
        else:
            entry.state = "unavailable" if snap.get("state") == "unavailable" else "failed"
            entry.last_error = (snap.get("error") or snap.get("reason") or "")[:300]
            entry.peer.collection_health = {"state": entry.state, "coverage": _coverage_report(entry.peer, entry)}
        entry.updated_at = clock.now()
        entry.save()
        entry.peer.save(update_fields=["collection_health"])
        results.append({"peer": entry.peer.label, "state": entry.state, "coverage": entry.peer.collection_health.get("coverage")})
    return results


def peer_collection_audit():
    """Document current pipeline capabilities for owner review."""
    return {
        "profile_snapshot": "meta_graph.business_discovery",
        "media_pagination": "meta_graph.business_discovery_media",
        "cursor_field": "PeerCollectionEntry.cursor.media_after",
        "manual_inspiration_in_pool": False,
    }


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
