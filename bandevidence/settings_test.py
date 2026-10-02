import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="band-evidence-test-"))
os.environ["BAND_EVIDENCE_DATA_ROOT"] = str(_root)
os.environ.setdefault("BAND_EVIDENCE_SECRET_KEY", "test-only-not-a-secret")

from .settings import *  # noqa: E402,F401,F403

DATA_ROOT = _root
DATABASES["default"]["NAME"] = _root / "app.sqlite3"  # noqa: F405
# A real file database, so locking and independent connections are exercised.
DATABASES["default"]["TEST"] = {"NAME": str(_root / "test.sqlite3")}  # noqa: F405
ALLOW_CLOCK_OVERRIDE = True
ALLOW_SYNTHETIC_SOURCES = True
LOGGING = {"version": 1, "disable_existing_loggers": False, "root": {"level": "WARNING"}}
