import os
from pathlib import Path

from django.conf import settings

SUBDIRS = ["imports", "assets", "datasets", "models", "reports", "cache", "backups", "run", "staging"]


def data_root() -> Path:
    return Path(settings.DATA_ROOT)


def ensure_layout(root: Path | None = None):
    root = root or data_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    for name in SUBDIRS:
        (root / name).mkdir(exist_ok=True)


def safe_path(relative: str, root: Path | None = None) -> Path:
    """Resolve a DB-stored relative path inside the data root, rejecting traversal and symlinks."""
    root = (root or data_root()).resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("Unsafe relative path")
    candidate = root.joinpath(rel)
    for parent in [candidate, *candidate.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("Symlinks are not allowed in the data root")
    resolved = candidate.resolve()
    if root not in resolved.parents:
        raise ValueError("Path escapes the data root")
    return resolved


def durable_write(target: Path, data: bytes):
    """Write via a temporary file, fsync, then atomic rename."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()
