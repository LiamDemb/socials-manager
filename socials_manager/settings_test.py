import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="socials-manager-test-"))
os.environ["SOCIALS_MANAGER_DATA_ROOT"] = str(_root)
os.environ.setdefault("SOCIALS_MANAGER_SECRET_KEY", "test-only-not-a-secret")

from .settings import *  # noqa: F403, E402

ALLOW_CLOCK_OVERRIDE = True
ALLOW_SYNTHETIC_SOURCES = True

# File-backed SQLite for concurrency tests (WAL + cross-connection locking behaviour).
DATABASES["default"]["TEST"] = {"NAME": str(_root / "test.sqlite3")}
