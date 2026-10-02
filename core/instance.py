import json
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import DomainError
from .paths import data_root, durable_write

SCHEMA_VERSION = 1
DEFAULTS = {
    "weekly_capacity_minutes": 600,
    "default_post_time": "18:00",
    "stale_after_days": 8,
    "baseline_max_gap_days": 7,
}


def instance_path():
    return data_root() / "instance.json"


def is_initialised():
    return instance_path().exists()


def validate_timezone(name):
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise DomainError("invalid_timezone", "Use an IANA timezone such as Australia/Perth.", fields={"timezone": "Unknown timezone"})
    return name


def load():
    path = instance_path()
    if not path.exists():
        raise DomainError("not_initialised", "This installation has not been initialised.", status=503)
    config = json.loads(path.read_text())
    if config.get("schema_version") != SCHEMA_VERSION:
        raise DomainError("instance_schema", "Unsupported instance.json schema version.", status=500)
    return {**DEFAULTS, **config}


def save(config):
    durable_write(instance_path(), (json.dumps(config, indent=2) + "\n").encode())


def create(own_artist_id, artist_label, timezone, fixture_class="owner"):
    if is_initialised():
        raise DomainError("already_initialised", "instance.json already exists; refusing to overwrite.")
    validate_timezone(timezone)
    config = {
        "schema_version": SCHEMA_VERSION,
        "instance_id": str(uuid.uuid4()),
        "own_artist_id": str(own_artist_id),
        "artist_label": artist_label,
        "timezone": timezone,
        "fixture_class": fixture_class,
        "bind_host": "127.0.0.1",
        "features": {
            "automatic_publication": False,
            "semantic_inference": False,
            "spotify_model_fitting": False,
            "validated_forecasts": False,
        },
        **DEFAULTS,
    }
    save(config)
    return config


def tz():
    return ZoneInfo(load()["timezone"])


def update(**changes):
    config = load()
    if "timezone" in changes:
        validate_timezone(changes["timezone"])
    config.update(changes)
    save(config)
    return config
