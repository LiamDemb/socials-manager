import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

from catalogue.services import create_object, create_own_artist, own_artist
from core import instance
from core.paths import ensure_layout
from sources.services import commit, ensure_spotify_source, preview_upload, set_mapping

AUDIENCE_HEADER = "date,listeners,monthly listeners,monthly active listeners,super listeners,streams,playlist adds,saves,followers"


def bootstrap(timezone_name="Australia/Perth", label="Test Band"):
    from sources.metric_registry import sync_definitions
    from sources.models import MetricDefinition

    ensure_layout()
    sync_definitions(MetricDefinition)  # TransactionTestCase flushes migration-seeded rows
    if not instance.is_initialised():
        instance.create(uuid.uuid4(), label, timezone_name, fixture_class="synthetic")
    else:
        instance.update(timezone=timezone_name)
    artist = own_artist() or create_own_artist(label)
    ensure_spotify_source()
    return artist


def key():
    return f"test-{uuid.uuid4()}"


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def audience_csv(rows):
    """rows: list of (date, listeners, monthly, active, super, streams, playlist_adds, saves, followers)."""
    lines = [AUDIENCE_HEADER] + [",".join(str(x) for x in r) for r in rows]
    return ("\ufeff" + "\n".join(lines) + "\n").encode()


def recording_csv(rows):
    return ("\ufeff" + "\n".join(["date,streams"] + [f"{d},{v}" for d, v in rows]) + "\n").encode()


def import_file(raw, name, recording=None, new_recording_label=None, approve_reason=None):
    from sources.services import approve_conflicts

    batch = preview_upload(raw, name)
    if batch.scope == "recording":
        if recording is not None:
            batch = set_mapping(batch.pk, batch.preview_revision, entity_id=recording.pk)
        else:
            batch = set_mapping(batch.pk, batch.preview_revision, new_recording_label=new_recording_label or "Song")
    if approve_reason:
        batch = approve_conflicts(batch.pk, batch.preview_revision, "all", approve_reason)
    return batch, commit(batch.pk, batch.preview_revision, key())


def recording(label="Song"):
    return create_object("recording", label)


def real_fixture(name):
    if settings.REAL_FIXTURES_DIR is None:
        return None
    path = Path(settings.REAL_FIXTURES_DIR) / name
    return path.read_bytes() if path.exists() else None
