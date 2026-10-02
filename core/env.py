"""Environment and data-root resolution. Supports legacy Socials Manager names during migration."""
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_project_env():
    """Load `.env` from the repository root without overwriting existing environment variables."""
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

LEGACY_DATA_ROOT = Path.home() / "Library" / "Application Support" / "BandEvidence"
DEFAULT_DATA_ROOT = Path.home() / "Library" / "Application Support" / "SocialsManager"

_ENV_ALIASES = {
    "DATA_ROOT": ("SOCIALS_MANAGER_DATA_ROOT", "BAND_EVIDENCE_DATA_ROOT"),
    "REAL_FIXTURES": ("SOCIALS_MANAGER_REAL_FIXTURES", "BAND_EVIDENCE_REAL_FIXTURES"),
    "SECRET_KEY": ("SOCIALS_MANAGER_SECRET_KEY", "BAND_EVIDENCE_SECRET_KEY"),
    "PORT": ("SOCIALS_MANAGER_PORT", "BAND_EVIDENCE_PORT"),
    "DEBUG": ("SOCIALS_MANAGER_DEBUG", "BAND_EVIDENCE_DEBUG"),
    "FROZEN_NOW": ("SOCIALS_MANAGER_FROZEN_NOW", "BAND_EVIDENCE_FROZEN_NOW"),
}


def env_first(*keys, default=None):
    for key in keys:
        val = os.environ.get(key)
        if val is not None and val != "":
            return val
    return default


def resolve_data_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    raw = env_first(*_ENV_ALIASES["DATA_ROOT"])
    if raw:
        return Path(raw).expanduser().resolve()
    new = DEFAULT_DATA_ROOT
    legacy = LEGACY_DATA_ROOT
    if new.exists() or not legacy.exists():
        return new
    return legacy


def resolve_real_fixtures_dir():
    raw = env_first(*_ENV_ALIASES["REAL_FIXTURES"])
    return Path(raw).expanduser() if raw else None
