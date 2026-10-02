"""Clearly labelled synthetic deliveries for evaluation mechanics. Refused in an owner instance."""
import hashlib
import math
import random
from datetime import datetime, time, timedelta, timezone

from django.conf import settings
from django.db import transaction

from catalogue.models import Entity
from core import clock, instance
from core.errors import DomainError
from sources.models import ImportBatch, Observation, ObservationContribution, ObservationVersion, RawFile, Source, SourcePolicyVersion
from sources.services import store_raw_file

ALL_ALLOWED = {p: "allowed" for p in ["collect", "store", "display", "descriptive_derive", "statistical_fit", "model_infer", "llm_ingest", "export"]}


def _guard():
    synthetic_instance = instance.is_initialised() and instance.load().get("fixture_class") == "synthetic"
    if not (settings.ALLOW_SYNTHETIC_SOURCES or synthetic_instance):
        raise DomainError("synthetic_refused", "Synthetic fixtures are not allowed in an owner installation.", status=403)


def synthetic_source():
    _guard()
    source, _ = Source.objects.get_or_create(
        provider="synthetic", route="fixture", defaults={"label": "Synthetic fixture (not real data)", "fixture_class": "synthetic"}
    )
    if not source.policies.exists():
        SourcePolicyVersion.objects.create(source=source, version=1, purposes=ALL_ALLOWED, assessment_ref="Synthetic fixture generated in code",
                                           effective_at=clock.now())
    return source


def synthetic_entity(label="Synthetic artist (fixture)"):
    _guard()
    return Entity.objects.get_or_create(kind="content", label=label, defaults={"created_at": clock.now()})[0]


def generate_series(start, days, seed=7, level=40.0, weekly=0.35, trend=0.002):
    rng = random.Random(seed)
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        mean = level * (1 + trend * i) * (1 + weekly * math.sin(2 * math.pi * d.weekday() / 7))
        out.append((d, max(0, int(round(rng.gauss(mean, mean * 0.15))))))
    return out


@transaction.atomic
def deliver(entity, metric_id, rows, available_at, revision_reason=""):
    """One synthetic delivery: creates or revises observations, available from `available_at`."""
    _guard()
    source = synthetic_source()
    policy = source.policies.order_by("-version").first()
    body = "\n".join(f"{d.isoformat()},{v}" for d, v in rows).encode()
    raw = store_raw_file(b"synthetic\n" + hashlib.sha256(body + str(available_at).encode()).hexdigest().encode() + b"\n" + body, "synthetic.csv")
    batch = ImportBatch.objects.create(
        source=source, policy_version=policy, raw_file=raw, original_name="synthetic.csv", scope="synthetic", mapped_entity=entity,
        parser_version="synthetic-v1", state="committed", created_at=available_at, committed_at=available_at,
    )
    for d, v in rows:
        obs, _ = Observation.objects.get_or_create(source=source, entity=entity, metric_id=metric_id, period_start=d,
                                                   period_end=d + timedelta(days=1), dimension_key="")
        current = obs.active_version
        if current and current.value == v:
            ObservationContribution.objects.get_or_create(version=current, batch=batch, defaults={"row_ref": d.isoformat()})
            continue
        ver = ObservationVersion.objects.create(
            observation=obs, version=(current.version + 1) if current else 1, value=v, available_at=available_at,
            policy_version=policy, source_row_ref=f"synthetic:{d.isoformat()}", supersedes=current, revision_reason=revision_reason,
        )
        ObservationContribution.objects.create(version=ver, batch=batch, row_ref=d.isoformat())
        obs.active_version = ver
        obs.save(update_fields=["active_version"])
    return batch


def deliver_daily(entity, metric_id, series, lag_days=1):
    """Each day's value becomes available `lag_days` after the day closes."""
    for d, v in series:
        at = datetime.combine(d + timedelta(days=lag_days), time(6, 0), tzinfo=timezone.utc)
        deliver(entity, metric_id, [(d, v)], at)
