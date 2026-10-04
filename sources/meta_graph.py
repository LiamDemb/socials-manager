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


def _public_error(res) -> dict:
    err = (res.data or {}).get("error", {}) if isinstance(getattr(res, "data", None), dict) else {}
    message = str(err.get("message") or res.error or "")
    for secret in (_graph_token() or "", _instagram_token() or ""):
        if secret:
            message = message.replace(secret, "[redacted]")
    return {"ok": bool(res.ok), "code": err.get("code"), "type": err.get("type"), "message": message[:400]}


def _instagram_json(path: str, token: str, params: dict) -> dict:
    """graph.instagram.com GET. Errors are redacted; callers must not store the URL."""
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    query = dict(params)
    query["access_token"] = token
    url = f"https://graph.instagram.com/{GRAPH_VERSION}/{path.lstrip('/')}?" + urllib.parse.urlencode(query)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return {"ok": True, "data": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        err = data.get("error") if isinstance(data, dict) else {}
        message = str((err or {}).get("message") or exc.reason or "")
        if token:
            message = message.replace(token, "[redacted]")
        return {"ok": False, "code": (err or {}).get("code"), "type": (err or {}).get("type"), "message": message[:400]}
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {exc}"[:400]}


def _field_presence(item: dict) -> dict:
    keys = ("id", "media_type", "media_url", "thumbnail_url", "permalink", "caption")
    return {
        "fields_present": sorted(k for k in keys if item.get(k)),
        "media_type": item.get("media_type"),
    }


def _probe_instagram_login_media() -> dict:
    token = _instagram_token()
    if not token:
        return {"state": "blocked", "reason": "INSTAGRAM_ACCESS_TOKEN is not set."}
    me = _instagram_json("me", token, {"fields": "user_id,username,account_type"})
    if not me.get("ok"):
        return {"state": "error", "code": me.get("code"), "type": me.get("type"), "message": me.get("message")}
    profile = me.get("data") or {}
    user_id = profile.get("user_id") or profile.get("id")
    if not user_id:
        return {"state": "blocked", "reason": "Instagram Login profile did not return a user id."}
    media = _instagram_json(
        f"{user_id}/media",
        token,
        {"fields": "id,media_type,media_url,thumbnail_url,permalink,caption", "limit": "1"},
    )
    if not media.get("ok"):
        return {"state": "error", "code": media.get("code"), "type": media.get("type"), "message": media.get("message")}
    item = ((media.get("data") or {}).get("data") or [{}])[0]
    return {
        "state": "ok",
        "username": profile.get("username"),
        "account_type": profile.get("account_type"),
        **_field_presence(item),
    }


def probe_media_fields(peer_username: str | None = None) -> dict:
    """Live field probe. Records presence of asset fields, not signed URLs or tokens."""
    cfg = inspect_configuration()
    graph_token = _graph_token()
    ig_id = cfg.get("instagram_business_account_id")
    report = {
        "graph_version": GRAPH_VERSION,
        "auth_route": cfg.get("auth_route"),
        "business_discovery_supported": cfg.get("business_discovery_supported"),
        "scopes": cfg.get("scopes") or [],
        "token_debug_ok": cfg.get("token_debug_ok"),
        "own_media": None,
        "instagram_login_own_media": None,
        "peer_media": None,
        "certified": False,
        "caching_or_inference_authorised": False,
    }
    if not graph_token or not ig_id:
        report["own_media"] = {"state": "blocked", "reason": cfg.get("detail")}
    else:
        own = graph_get(
            f"{ig_id}/media",
            graph_token,
            {"fields": "id,media_type,media_url,thumbnail_url,permalink,caption", "limit": "1"},
        )
        if own.ok:
            item = ((own.data or {}).get("data") or [{}])[0]
            report["own_media"] = {"state": "ok", **_field_presence(item)}
        else:
            report["own_media"] = {"state": "error", **_public_error(own)}
    report["instagram_login_own_media"] = _probe_instagram_login_media()
    if not peer_username:
        report["peer_media"] = {"state": "not_run", "reason": "No peer username was supplied."}
    elif not cfg.get("business_discovery_supported"):
        report["peer_media"] = {"state": "blocked", "reason": "Business Discovery is not available with this token route."}
    elif not graph_token or not ig_id:
        report["peer_media"] = {"state": "blocked", "reason": cfg.get("detail")}
    else:
        field = (
            f"business_discovery.username({peer_username})"
            "{media.limit(1){id,media_type,media_url,thumbnail_url,permalink,caption}}"
        )
        peer = graph_get(ig_id, graph_token, {"fields": field})
        if not peer.ok:
            report["peer_media"] = {"state": "error", "peer_username": peer_username, **_public_error(peer)}
        else:
            media = (((peer.data or {}).get("business_discovery") or {}).get("media") or {}).get("data") or []
            item = media[0] if media else {}
            report["peer_media"] = {
                "state": "ok" if item else "empty",
                "peer_username": peer_username,
                **_field_presence(item),
            }
    return report


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
