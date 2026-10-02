"""Meta Graph API: inspect app configuration, own Instagram account, and Business Discovery for peers."""
from core.env import env_first
from core.provider_http import graph_get
from sources.api_cache import store

GRAPH_VERSION = env_first("META_GRAPH_VERSION", default="v21.0")


def _instagram_token():
    return env_first("INSTAGRAM_ACCESS_TOKEN")


def _graph_token():
    """Facebook Graph API (Pages, IG business account, Business Discovery). Never use Instagram Login tokens here."""
    return env_first("META_ACCESS_TOKEN")


def _instagram_basic_me(token):
    import urllib.parse
    import urllib.request

    version = GRAPH_VERSION
    url = f"https://graph.instagram.com/{version}/me?" + urllib.parse.urlencode(
        {"fields": "user_id,username,account_type", "access_token": token}
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            import json

            return json.loads(resp.read())
    except Exception:
        return None


def inspect_configuration():
    """Determine which auth route and capabilities the configured app actually has."""
    graph_token = _graph_token()
    ig_token = _instagram_token()
    app_id = env_first("META_APP_ID")
    if not graph_token and not ig_token:
        return {
            "live_integration": "Blocked",
            "auth_route": "unknown",
            "detail": "Set INSTAGRAM_ACCESS_TOKEN and/or META_ACCESS_TOKEN in .env (never commit it).",
            "business_discovery_supported": False,
            "app_id_present": bool(app_id),
            "graph_token_present": False,
            "instagram_token_present": False,
        }
    debug = None
    pages = None
    if graph_token:
        debug = graph_get("debug_token", graph_token, {"input_token": graph_token})
        graph_get("me", graph_token, {"fields": "id,name"})
        pages = graph_get("me/accounts", graph_token, {"fields": "id,name,instagram_business_account"})
    route = "facebook_login_graph"
    ig_user_id = None
    ig_username = None
    page_id = None
    bd_supported = False
    detail = []
    ig_basic = _instagram_basic_me(ig_token) if ig_token else None
    if ig_basic and ig_basic.get("user_id"):
        ig_user_id = ig_basic.get("user_id")
        ig_username = ig_basic.get("username")
        detail.append("Instagram Login token resolves own profile via graph.instagram.com.")
    if pages and pages.ok and pages.data and pages.data.get("data"):
        for p in pages.data["data"]:
            iba = (p.get("instagram_business_account") or {}).get("id")
            if iba:
                page_id = p.get("id")
                ig_user_id = iba
                route = "facebook_login_graph"
                detail.append(f"Page {p.get('name')} linked to Instagram business account {iba}")
                break
    elif graph_token and not page_id:
        detail.append(
            "META_ACCESS_TOKEN did not return a Page with instagram_business_account (check pages_show_list and Page admin)."
        )
    if not ig_user_id:
        detail.append(
            "No Instagram business account resolved. Link a Facebook Page to the professional account or set INSTAGRAM_ACCESS_TOKEN."
        )
    elif graph_token and page_id:
        prof = graph_get(ig_user_id, graph_token, {"fields": "username,name,followers_count,media_count"})
        if prof.ok and prof.data:
            ig_username = prof.data.get("username")
            store("meta", f"own:{ig_user_id}", prof.data)
        bd_supported = bool(ig_user_id and page_id)
    elif ig_basic and ig_basic.get("user_id") and not page_id:
        route = "instagram_login_basic"
        detail.append("Business Discovery requires META_ACCESS_TOKEN with Page access (see docs/META-SETUP.md).")
    scopes = []
    if debug and debug.ok and debug.data and debug.data.get("data"):
        scopes = debug.data["data"].get("scopes") or []
    report = {
        "live_integration": "Passed" if ig_user_id else "Blocked",
        "own_account_route": route,
        "auth_route": route,
        "graph_version": GRAPH_VERSION,
        "app_id_present": bool(app_id),
        "graph_token_present": bool(graph_token),
        "instagram_token_present": bool(ig_token),
        "token_debug_ok": bool(debug and debug.ok),
        "scopes": scopes,
        "instagram_business_account_id": ig_user_id,
        "instagram_username": ig_username,
        "facebook_page_id": page_id,
        "business_discovery_supported": bd_supported,
        "detail": "; ".join(detail) or "Inspect Pages and permissions in Meta developer console.",
        "instagram_login_only_warning": (
            "Instagram Login token is for graph.instagram.com only. Peer discovery uses META_ACCESS_TOKEN on graph.facebook.com."
        ),
    }
    store("meta", "inspect", report)
    return report


def fetch_own_account():
    cfg = inspect_configuration()
    graph_token = _graph_token()
    ig_token = _instagram_token()
    ig_id = cfg.get("instagram_business_account_id")
    page_id = cfg.get("facebook_page_id")

    if graph_token and ig_id and page_id:
        fields = "username,name,followers_count,follows_count,media_count,biography,profile_picture_url"
        res = graph_get(ig_id, graph_token, {"fields": fields})
        if res.ok:
            store("meta", f"own_account:{ig_id}", res.data)
            data = res.data or {}
            available = {k: data.get(k) for k in data.keys()}
            unavailable = [f for f in fields.split(",") if f not in data]
            return {
                "state": "ok",
                "account_id": ig_id,
                "fields": available,
                "unavailable_fields": unavailable,
                "source": "facebook_graph",
            }
        err = (res.data or {}).get("error", {}) if isinstance(res.data, dict) else {}
        if not ig_token:
            return {"state": "error", "error": err.get("message", res.error), "unavailable_fields": [fields]}

    if ig_token and ig_id:
        ig_basic = _instagram_basic_me(ig_token)
        if ig_basic:
            store("meta", f"own_ig_basic:{ig_id}", ig_basic)
            unavailable = ["followers_count", "media_count", "insights"]
            note = "Instagram Login route exposes limited profile fields."
            if graph_token and not page_id:
                note += " META_ACCESS_TOKEN could not list a linked Facebook Page for full metrics and peer discovery."
            elif not graph_token:
                note += " Set META_ACCESS_TOKEN (Facebook Graph user or Page token) for full metrics and peer discovery."
            return {
                "state": "ok",
                "account_id": ig_id,
                "fields": {k: ig_basic.get(k) for k in ("user_id", "username", "account_type")},
                "unavailable_fields": unavailable,
                "source": "instagram_login_basic",
                "note": note,
            }

    if not ig_id:
        return {"state": "blocked", "reason": cfg.get("detail"), "fields": {}}
    return {"state": "blocked", "reason": cfg.get("detail") or "No usable token.", "fields": {}}


def business_discovery(peer_username: str):
    cfg = inspect_configuration()
    graph_token = _graph_token()
    ig_id = cfg.get("instagram_business_account_id")
    if not cfg.get("business_discovery_supported"):
        return {
            "state": "blocked",
            "reason": "Business Discovery not available with current app configuration. See docs/META-SETUP.md.",
            "peer_username": peer_username,
        }
    if not graph_token:
        return {
            "state": "blocked",
            "reason": "META_ACCESS_TOKEN required for Business Discovery on graph.facebook.com.",
            "peer_username": peer_username,
        }
    field = f"business_discovery.username({peer_username}){{username,name,biography,followers_count,media_count,profile_picture_url}}"
    res = graph_get(ig_id, graph_token, {"fields": field})
    if not res.ok:
        err = (res.data or {}).get("error", {}) if isinstance(res.data, dict) else {}
        return {"state": "error", "peer_username": peer_username, "error": err.get("message", res.error), "error_code": err.get("code")}
    store("meta", f"bd:{peer_username}", res.data)
    bd = (res.data or {}).get("business_discovery") or {}
    if not bd:
        return {"state": "unavailable", "peer_username": peer_username, "reason": "Empty business_discovery payload (account may be ineligible or private)."}
    return {
        "state": "ok",
        "peer_username": peer_username,
        "fields": {k: bd.get(k) for k in bd if k != "id"},
        "unavailable_fields": ["reach", "saves", "online_followers", "conversions"],
        "source": "business_discovery",
        "note": "Public profile fields only; no fabricated reach or conversion metrics.",
    }


def business_discovery_media(peer_username: str, after: str | None = None, limit: int = 25):
    """Paginated public media list for a peer account."""
    cfg = inspect_configuration()
    graph_token = _graph_token()
    ig_id = cfg.get("instagram_business_account_id")
    if not cfg.get("business_discovery_supported") or not graph_token:
        return {"state": "blocked", "reason": "Business Discovery unavailable", "peer_username": peer_username}
    media_fields = "id,caption,media_type,permalink,timestamp,like_count,comments_count"
    paging = f",media.limit({limit}){{ {media_fields} }}"
    if after:
        paging = f",media.after({after}).limit({limit}){{ {media_fields} }}"
    field = f"business_discovery.username({peer_username}){{username,media_count{paging}}}"
    res = graph_get(ig_id, graph_token, {"fields": field})
    if not res.ok:
        err = (res.data or {}).get("error", {}) if isinstance(res.data, dict) else {}
        return {"state": "error", "error": err.get("message", res.error)}
    bd = (res.data or {}).get("business_discovery") or {}
    media = bd.get("media") or {}
    items = media.get("data") or []
    cursors = (media.get("paging") or {}).get("cursors") or {}
    return {
        "state": "ok",
        "peer_username": peer_username,
        "media_count_reported": bd.get("media_count"),
        "items": items,
        "next_after": cursors.get("after"),
    }
