import uuid

from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_kind = models.CharField(max_length=40)
    entity_id = models.CharField(max_length=64)
    revision = models.IntegerField(null=True)
    action = models.CharField(max_length=60)
    actor = models.CharField(max_length=30, default="local-owner")
    recorded_at = models.DateTimeField()
    details = models.JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=["entity_kind", "entity_id", "recorded_at"])]
        ordering = ["recorded_at"]


class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=100, primary_key=True)
    action = models.CharField(max_length=60)
    response = models.JSONField()
    created_at = models.DateTimeField()


class OutboxEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=60)
    fingerprint = models.CharField(max_length=128, unique=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    handled_at = models.DateTimeField(null=True)


class Job(models.Model):
    STATES = [(s, s) for s in ["queued", "leased", "done", "failed", "dead", "cancelled"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.CharField(max_length=60)
    scope_key = models.CharField(max_length=120)
    input_key = models.CharField(max_length=120)
    state = models.CharField(max_length=12, choices=STATES, default="queued")
    due_at = models.DateTimeField()
    lease_owner = models.CharField(max_length=80, null=True, blank=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    safe_error = models.CharField(max_length=300, blank=True, default="")
    cursor = models.JSONField(null=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "scope_key", "input_key"], name="job_unique_slot")]
        indexes = [models.Index(fields=["state", "due_at"])]


class WorkerHeartbeat(models.Model):
    worker_id = models.CharField(max_length=80, primary_key=True)
    seen_at = models.DateTimeField()
    pid = models.IntegerField()


class BackupRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField()
    relative_path = models.CharField(max_length=300)
    reason = models.CharField(max_length=60)
    status = models.CharField(max_length=20)
    detail = models.JSONField(default=dict)
