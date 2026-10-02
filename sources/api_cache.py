"""Persist provider JSON for lineage (secrets stripped before write)."""
import hashlib
import json
from pathlib import Path

from core import clock
from core.paths import data_root, durable_write


def _strip_secrets(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = k.lower()
            if lk in ("access_token", "token", "secret", "password") or "token" in lk:
                out[k] = "[redacted]"
            else:
                out[k] = _strip_secrets(v)
        return out
    if isinstance(obj, list):
        return [_strip_secrets(x) for x in obj]
    return obj


def store(provider: str, key: str, payload) -> str:
    root = data_root() / "cache" / "api" / provider
    root.mkdir(parents=True, exist_ok=True)
    safe = _strip_secrets(payload)
    body = json.dumps({"fetched_at": clock.now().isoformat(), "key": key, "payload": safe}, indent=2).encode()
    digest = hashlib.sha256(f"{provider}:{key}".encode()).hexdigest()[:16]
    path = root / f"{digest}.json"
    durable_write(path, body)
    return str(path.relative_to(data_root()))
