"""Bounded media blob storage under the data root (section 5)."""
import hashlib
from pathlib import Path

from core.paths import data_root, durable_write, safe_path

from .media_config import QUOTAS
from .models import MediaAsset


def media_root() -> Path:
    root = data_root() / "media" / "blobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def playback_root() -> Path:
    root = data_root() / "media" / "playback"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dir_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for p in root.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def usage_bytes() -> int:
    return _dir_bytes(media_root())


def usage_report() -> dict:
    return {
        "preview_analysis_bytes": usage_bytes(),
        "preview_analysis_quota": QUOTAS["preview_analysis_bytes"],
        "playback_cache_bytes": _dir_bytes(playback_root()),
        "playback_cache_quota": QUOTAS["playback_cache_bytes"],
    }


def quota_allows(additional: int, kind="preview") -> tuple[bool, str]:
    if kind == "playback":
        used = _dir_bytes(playback_root())
        cap = QUOTAS["playback_cache_bytes"]
    else:
        used = usage_bytes()
        cap = QUOTAS["preview_analysis_bytes"]
    if used + additional > cap:
        return False, "quota_exceeded"
    return True, ""


def store_blob(data: bytes, ext: str = "bin", kind="preview") -> tuple[str, str]:
    ok, reason = quota_allows(len(data), kind=kind)
    if not ok:
        raise ValueError(reason)
    digest = hashlib.sha256(data).hexdigest()
    prefix = digest[:2]
    folder = "media/playback" if kind == "playback" else "media/blobs"
    rel = f"{folder}/{prefix}/{digest}.{ext}"
    target = safe_path(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        durable_write(target, data)
    return digest, rel


def read_bounded(chunks, cap: int) -> bytes:
    """Stream-count bytes and abort at the cap. Caller deletes temps."""
    out = bytearray()
    for chunk in chunks:
        if len(out) + len(chunk) > cap:
            raise ValueError("transient_cap_exceeded")
        out.extend(chunk)
    return bytes(out)


def orphan_relative_paths() -> list[str]:
    db_paths = set(MediaAsset.objects.exclude(relative_path="").values_list("relative_path", flat=True))
    orphans = []
    root = data_root()
    for base in (media_root(), playback_root()):
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if rel not in db_paths:
                orphans.append(rel)
    return orphans


def evict_playback(max_remove: int = 20) -> dict:
    """Unused playback proxies first. Does not delete analysis blobs or external originals."""
    removed = []
    root = data_root()
    files = sorted(playback_root().rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0)
    for p in files:
        if not p.is_file() or len(removed) >= max_remove:
            continue
        rel = str(p.relative_to(root))
        linked = MediaAsset.objects.filter(relative_path=rel, role="playback_proxy").exists()
        if linked:
            continue
        p.unlink()
        removed.append(rel)
    return {"removed": removed, "usage": usage_report()}
