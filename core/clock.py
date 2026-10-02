import os
from datetime import datetime, timezone

from django.conf import settings

_override = None


def now():
    if settings.ALLOW_CLOCK_OVERRIDE:
        if _override is not None:
            return _override
        frozen = os.environ.get("BAND_EVIDENCE_FROZEN_NOW")
        if frozen:
            return datetime.fromisoformat(frozen.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


class frozen:
    """Context manager for tests: freeze the application clock at an aware instant."""

    def __init__(self, instant):
        if instant.tzinfo is None:
            raise ValueError("Frozen clock needs an aware datetime")
        self.instant = instant.astimezone(timezone.utc)

    def __enter__(self):
        global _override
        self._previous = _override
        _override = self.instant
        return self.instant

    def __exit__(self, *exc):
        global _override
        _override = self._previous
        return False
