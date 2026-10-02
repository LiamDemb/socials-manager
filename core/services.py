import hashlib
import json
import re
from datetime import timedelta

from django.db import IntegrityError, transaction

from . import clock
from .errors import DomainError, StaleRevision
from .models import AuditEvent, IdempotencyRecord, Job, OutboxEvent

IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_\-:.]{8,100}$")


def audit(entity_kind, entity_id, action, details=None, revision=None, actor="local-owner"):
    return AuditEvent.objects.create(
        entity_kind=entity_kind,
        entity_id=str(entity_id),
        action=action,
        details=details or {},
        revision=revision,
        actor=actor,
        recorded_at=clock.now(),
    )


def check_idempotency_key(key):
    if not key or not IDEMPOTENCY_KEY.match(key):
        raise DomainError("idempotency_key_required", "A valid Idempotency-Key is required for this action.")
    return key


def idempotent(key, action, fn):
    """Run fn() once per key inside one transaction; replay returns the stored response."""
    check_idempotency_key(key)
    existing = IdempotencyRecord.objects.filter(key=key).first()
    if existing:
        if existing.action != action:
            raise DomainError("idempotency_key_reused", "This Idempotency-Key was used for a different action.", status=409)
        return existing.response
    try:
        with transaction.atomic():
            response = fn()
            IdempotencyRecord.objects.create(key=key, action=action, response=response, created_at=clock.now())
            return response
    except IntegrityError:
        existing = IdempotencyRecord.objects.filter(key=key).first()
        if existing and existing.action == action:
            return existing.response
        raise


def conditional_update(model, pk, expected_revision, what="record", **fields):
    """Optimistic revision update; SQLite has no row locks, so the WHERE clause is the guard."""
    from django.db.models import F

    updated = model.objects.filter(pk=pk, revision=expected_revision).update(revision=F("revision") + 1, **fields)
    if updated != 1:
        raise StaleRevision(what)
    return expected_revision + 1


def emit(kind, payload):
    body = json.dumps(payload, sort_keys=True, default=str)
    fingerprint = hashlib.sha256(f"{kind}:{body}".encode()).hexdigest()
    event, _ = OutboxEvent.objects.get_or_create(
        fingerprint=fingerprint, defaults={"kind": kind, "payload": payload, "created_at": clock.now()}
    )
    return event


def enqueue(task, scope_key, input_key, due_at=None, max_attempts=3):
    job, _ = Job.objects.get_or_create(
        task=task,
        scope_key=scope_key,
        input_key=input_key,
        defaults={"due_at": due_at or clock.now(), "max_attempts": max_attempts},
    )
    return job


def claim_next_job(worker_id, lease_seconds=300):
    """Claim one due job with a conditional update. Expired leases are recoverable."""
    now = clock.now()
    candidates = Job.objects.filter(due_at__lte=now).filter(
        state="queued"
    ) | Job.objects.filter(state="leased", lease_until__lt=now)
    for job in candidates.order_by("due_at")[:5]:
        claimed = Job.objects.filter(pk=job.pk, state=job.state, lease_until=job.lease_until).update(
            state="leased", lease_owner=worker_id, lease_until=now + timedelta(seconds=lease_seconds), attempts=job.attempts + 1
        )
        if claimed == 1:
            return Job.objects.get(pk=job.pk)
    return None


def finish_job(job, worker_id, error=None, retry_after_seconds=60):
    now = clock.now()
    qs = Job.objects.filter(pk=job.pk, lease_owner=worker_id, state="leased")
    if error is None:
        return qs.update(state="done", finished_at=now, safe_error="", lease_owner=None, lease_until=None)
    if job.attempts >= job.max_attempts:
        return qs.update(state="dead", safe_error=str(error)[:300], finished_at=now, lease_owner=None, lease_until=None)
    backoff = retry_after_seconds * (2 ** (job.attempts - 1))
    return qs.update(
        state="queued", safe_error=str(error)[:300], due_at=now + timedelta(seconds=backoff), lease_owner=None, lease_until=None
    )
