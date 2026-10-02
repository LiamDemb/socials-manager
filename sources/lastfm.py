"""Last.fm discovery adapter. Similarity is a candidate signal, not campaign evidence."""
from core.provider_http import lastfm_get
from sources.api_cache import store

LF_PROVIDER = "lastfm"
LF_ROUTE = "audioscrobbler_api"


def artist_get_similar(name, limit=30):
    res = lastfm_get("artist.getSimilar", artist=name, limit=str(limit))
    if not res.ok or not res.data:
        return {"state": "error", "error": res.error or f"HTTP {res.status}", "similar": []}
    if res.data.get("error"):
        return {"state": "error", "error": res.data.get("message", "Last.fm error"), "similar": []}
    store(LF_PROVIDER, f"similar:{name}", res.data)
    sim = (res.data.get("similarartists") or {}).get("artist") or []
    out = []
    for a in sim:
        out.append({
            "name": a.get("name"),
            "match": float(a.get("match", 0) or 0),
            "url": a.get("url"),
            "mbid": (a.get("mbid") or "").strip() or None,
            "discovery_note": "Last.fm similarity only; confirm identity and relevance before peer promotion.",
        })
    return {"state": "found", "seed_artist": name, "similar": out}
