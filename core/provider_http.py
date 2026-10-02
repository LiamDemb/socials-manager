"""Minimal HTTP client for provider adapters (stdlib only). Rate limits and identification per provider policy."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from core.env import env_first

MB_USER_AGENT = "SocialsManager/0.2 (+https://localhost; contact=owner@local)"
_last_mb_call = 0.0


@dataclass
class HttpResult:
    ok: bool
    status: int
    data: dict | list | None
    error: str = ""
    headers: dict = field(default_factory=dict)


def _request(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            parsed = json.loads(body) if "json" in ctype or body[:1] in (b"{", b"[") else None
            return HttpResult(True, resp.status, parsed, headers=dict(resp.headers))
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = None
        return HttpResult(False, exc.code, payload, error=str(exc))
    except urllib.error.URLError as exc:
        return HttpResult(False, 0, None, error=str(exc.reason))


def musicbrainz_get(path, params=None):
    """MusicBrainz WS/2: max 1 request per second; User-Agent required."""
    global _last_mb_call
    wait = 1.05 - (time.time() - _last_mb_call)
    if wait > 0:
        time.sleep(wait)
    _last_mb_call = time.time()
    base = "https://musicbrainz.org/ws/2/"
    q = urllib.parse.urlencode({**(params or {}), "fmt": "json"})
    url = f"{base}{path}?{q}" if q else f"{base}{path}"
    return _request(url, headers={"User-Agent": MB_USER_AGENT, "Accept": "application/json"})


def lastfm_get(method, **params):
    key = env_first("LAST_FM_API_KEY")
    if not key:
        return HttpResult(False, 0, None, error="LAST_FM_API_KEY not set")
    params = {"method": method, "api_key": key, "format": "json", **params}
    url = "https://ws.audioscrobbler.com/2.0/?" + urllib.parse.urlencode(params)
    return _request(url)


def graph_get(path, access_token, params=None):
    version = env_first("META_GRAPH_VERSION", default="v21.0")
    q = {"access_token": access_token, **(params or {})}
    url = f"https://graph.facebook.com/{version}/{path}?" + urllib.parse.urlencode(q)
    return _request(url)
