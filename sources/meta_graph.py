"""Meta Graph API: inspect app configuration, own Instagram account, and Business Discovery for peers."""
from core.env import env_first
from core.provider_http import graph_get
from sources.api_cache import store

GRAPH_VERSION = env_first("META_GRAPH_VERSION", default="v21.0")


def _token():
    return env_first("INSTAGRAM_ACCESS_TOKEN", "META_ACCESS_TOKEN")


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
    token = _token()
    ig_token = env_first("INSTAGRAM_ACCESS_TOKEN")
    app_id = env_first("META_APP_ID")
    if not token:
        return {
            "live_integration": "Blocked",
            "auth_route": "unknown",
            "detail": "Set INSTAGRAM_ACCESS_TOKEN or META_ACCESS_TOKEN in .env (never commit it).",
            "business_discovery_supported": False,
            "app_id_present": bool(app_id),
        }
    debug = graph_get("debug_token", token, {"input_token": token}) if env_first("META_ACCESS_TOKEN") else None
    me = graph_get("me", token, {"fields": "id,name"})
    pages = graph_get("me/accounts", token, {"fields": "id,name,instagram_business_account"})
    route = "facebook_login_graph"
    ig_user_id = None
    ig_username = None
    page_id = None
    bd_supported = False
    detail = []
    ig_basic = _instagram_basic_me(ig_token) if ig_token else None
    if ig_basic and ig_basic.get("user_id"):
        route = "instagram_login_basic"
        ig_user_id = ig_basic.get("user_id")
        ig_username = ig_basic.get("username")
        detail.append("Instagram Login token resolves own profile via graph.instagram.com (Business Discovery still requires Facebook Page link).")
    if pages.ok and pages.data and pages.data.get("data"):
        for p in pages.data["data"]:
            iba = (p.get("instagram_business_account") or {}).get("id")
            if iba:
                page_id = p.get("id")
                ig_user_id = iba
                detail.append(f"Page {p.get('name')} linked to Instagram business account {iba}")
                break
    if not ig_user_id:
        detail.append("No instagram_business_account on connected Pages. Business Discovery requires Facebook Login + Page-linked professional account, not Instagram Login-only.")
    else:
        prof = graph_get(ig_user_id, token, {"fields": "username,name,followers_count,media_count"})
        if prof.ok and prof.data:
            ig_username = prof.data.get("username")
            store("meta", f"own:{ig_user_id}", prof.data)
        bd_supported = bool(ig_user_id and page_id)
    scopes = []
    if debug and debug.ok and debug.data and debug.data.get("data"):
        scopes = debug.data["data"].get("scopes") or []
    report = {
        "live_integration": "Passed" if ig_user_id else "Blocked",
        "own_account_route": route,
        "auth_route": route,
        "graph_version": GRAPH_VERSION,
        "app_id_present": bool(app_id),
        "token_debug_ok": bool(debug and debug.ok),
        "scopes": scopes,
        "instagram_business_account_id": ig_user_id,
        "instagram_username": ig_username,
        "facebook_page_id": page_id,
        "business_discovery_supported": bd_supported,
        "detail": "; ".join(detail) or "Inspect Pages and permissions in Meta developer console.",
        "instagram_login_only_warning": "Instagram Login product selection alone does not enable Business Discovery. Connect a Facebook Page and use Graph API with a Page token.",
    }
    store("meta", "inspect", report)
    return report


def fetch_own_account():
    cfg = inspect_configuration()
    token = _token()
    ig_id = cfg.get("instagram_business_account_id")
    if cfg.get("auth_route") == "instagram_login_basic" and ig_id:
        ig_basic = _instagram_basic_me(env_first("INSTAGRAM_ACCESS_TOKEN"))
        if ig_basic:
            store("meta", f"own_ig_basic:{ig_id}", ig_basic)
            return {
                "state": "ok",
                "account_id": ig_id,
                "fields": {k: ig_basic.get(k) for k in ("user_id", "username", "account_type")},
                "unavailable_fields": ["followers_count", "media_count", "insights"],
                "source": "instagram_login_basic",
                "note": "Instagram Login route exposes limited profile fields; connect a Facebook Page for Graph insights and Business Discovery.",
            }
    if not token or not ig_id:
        return {"state": "blocked", "reason": cfg.get("detail"), "fields": {}}
    fields = "username,name,followers_count,follows_count,media_count,biography,profile_picture_url"
    res = graph_get(ig_id, token, {"fields": fields})
    if not res.ok:
        err = (res.data or {}).get("error", {}) if isinstance(res.data, dict) else {}
        return {"state": "error", "error": err.get("message", res.error), "unavailable_fields": [fields]}
    store("meta", f"own_account:{ig_id}", res.data)
    data = res.data or {}
    available = {k: data.get(k) for k in data.keys()}
    unavailable = [f for f in fields.split(",") if f not in data]
    return {"state": "ok", "account_id": ig_id, "fields": available, "unavailable_fields": unavailable, "source": "own_account"}


def business_discovery(peer_username: str):
    cfg = inspect_configuration()
    token = _token()
    ig_id = cfg.get("instagram_business_account_id")
    if not cfg.get("business_discovery_supported"):
        return {
            "state": "blocked",
            "reason": "Business Discovery not available with current app configuration. See docs/META-SETUP.md.",
            "peer_username": peer_username,
        }
    field = f"business_discovery.username({peer_username}){{username,name,biography,followers_count,media_count,profile_picture_url}}"
    res = graph_get(ig_id, token, {"fields": field})
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
