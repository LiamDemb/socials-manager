"""Bounded MusicBrainz lookups for identity and disambiguation. No automatic merge of ambiguous artists."""
from core.provider_http import musicbrainz_get
from sources.api_cache import store

MB_PROVIDER = "musicbrainz"
MB_ROUTE = "ws_api"


def search_artists(name, limit=5):
    res = musicbrainz_get("artist", {"query": f'artist:"{name}"', "limit": str(limit)})
    if not res.ok or not res.data:
        return {"state": "error", "error": res.error or f"HTTP {res.status}", "candidates": []}
    artists = res.data.get("artists") or []
    store(MB_PROVIDER, f"search:{name}", res.data)
    candidates = []
    for a in artists:
        candidates.append({
            "mbid": a.get("id"),
            "name": a.get("name"),
            "sort_name": a.get("sort-name"),
            "disambiguation": a.get("disambiguation") or "",
            "country": a.get("country"),
            "score": a.get("score"),
            "url": f"https://musicbrainz.org/artist/{a.get('id')}" if a.get("id") else "",
        })
    state = "ambiguous" if len(candidates) > 1 else ("found" if candidates else "not_found")
    return {"state": state, "candidates": candidates, "query": name}


def lookup_artist(mbid):
    res = musicbrainz_get(f"artist/{mbid}", {"inc": "url-rels+artist-rels"})
    if not res.ok or not res.data:
        return {"state": "error", "error": res.error or f"HTTP {res.status}"}
    store(MB_PROVIDER, f"artist:{mbid}", res.data)
    a = res.data
    rels = []
    for r in (a.get("relations") or [])[:20]:
        if r.get("artist"):
            rels.append({"type": r.get("type"), "artist": r["artist"].get("name"), "mbid": r["artist"].get("id")})
    return {
        "state": "found",
        "mbid": a.get("id"),
        "name": a.get("name"),
        "disambiguation": a.get("disambiguation") or "",
        "country": a.get("country"),
        "life_span": a.get("life-span"),
        "relations": rels,
        "url": f"https://musicbrainz.org/artist/{a.get('id')}",
    }


def lookup_release(mbid):
    res = musicbrainz_get(f"release/{mbid}", {"inc": "artist-credits+recordings"})
    if not res.ok or not res.data:
        return {"state": "error", "error": res.error or f"HTTP {res.status}"}
    store(MB_PROVIDER, f"release:{mbid}", res.data)
    r = res.data
    return {
        "state": "found",
        "mbid": r.get("id"),
        "title": r.get("title"),
        "date": r.get("date"),
        "country": r.get("country"),
        "artists": [c.get("name") for c in (r.get("artist-credit") or [])],
        "url": f"https://musicbrainz.org/release/{r.get('id')}",
    }
